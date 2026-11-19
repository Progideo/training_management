"""Public general information, with optional offers supplied by each application."""

import json
from urllib.parse import quote, urlencode

from dateutil.relativedelta import relativedelta

from markupsafe import Markup

from odoo import fields, http
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request
from odoo.tools import format_date, is_html_empty
from odoo.tools.misc import formatLang

CARDS_PER_PAGE = 12
FORMAT_LABELS = {"inter": "Inter-entreprises", "intra": "Intra-entreprise", "autonomous": "En autonomie"}


class StructuredData(dict):
    """schema.org data, serialised when the page renders, once every application has completed it."""

    def __html__(self):
        text = json.dumps(self, ensure_ascii=False, default=str)
        # Inside <script>, only these characters could close or alter the element.
        return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


class TrainingCatalogue(http.Controller):
    @staticmethod
    def _rows():
        # The website selects its operating company; never take one from a URL.
        website = request.env.website
        return request.env["training.course"]._catalogue_rows(website.company_id if website else request.env.company)

    def _catalogue_options(self, **kwargs):
        return {}

    @staticmethod
    def _course_path(course_id, name):
        """Canonical public address of a course: its name, then its identifier."""
        return "/formations/catalogue/" + request.env["ir.http"]._slug((course_id, name))

    @classmethod
    def _linked(cls, row):
        """Row with its canonical address; offer links to the course page follow it."""
        path = cls._course_path(row["id"], row["name"])
        prefix = "/formations/catalogue/%s?" % row["id"]
        offers = [
            {**offer, "url": path + "?" + offer["url"][len(prefix) :]}
            if offer.get("url", "").startswith(prefix)
            else offer
            for offer in row["offers"]
        ]
        return {**row, "url": path, "offers": offers}

    # Facet values are fixed keys: visitor input never reaches a domain or a template unchecked.
    DURATIONS = ("short", "medium", "long")
    SORTS = ("relevance", "next", "price", "duration", "new")

    @staticmethod
    def _formats(row):
        """Ways to follow a course, from the facts its applications project."""
        return {
            "inter": bool(row.get("next_session")),
            "intra": bool(row.get("live")),
            "autonomous": bool(
                row.get("autonomous")
                or row.get("elearning")
                or any(offer["mode"] == "autonomous" for offer in row["offers"])
            ),
        }

    @staticmethod
    def _duration_bucket(days):
        if not days:
            return ""
        return "short" if days <= 1 else "medium" if days <= 3 else "long"

    @staticmethod
    def _min_price(row):
        prices = [
            price["amount"] for price in (row.get("session_price"), (row.get("autonomous") or {}).get("price")) if price
        ]
        return min(prices) if prices else None

    def _facet_match(self, row, facets, skip=None):
        soon_limit = fields.Datetime.now() + relativedelta(months=3)
        checks = {
            "category": lambda: str(row["category_id"]) == facets["category"],
            "mode": lambda: any(facets["mode"] in offer.get("modes", [offer["mode"]]) for offer in row["offers"]),
            "format": lambda: self._formats(row).get(facets["format"], False),
            "level": lambda: row.get("level_key") == facets["level"],
            "duration": lambda: self._duration_bucket(row.get("duration_days")) == facets["duration"],
            "certifying": lambda: bool(row.get("certifying")),
            "soon": lambda: bool(row.get("next_session") and row["next_session"]["start_at"] <= soon_limit),
            "remote": lambda: bool({"remote", "blended"} & set(row.get("live_modes") or [])),
        }
        return all(checks[key]() for key, value in facets.items() if value and key != skip)

    def _catalogue_url(self, options, page=1, **changes):
        args = {key: value for key, value in {**options, **changes}.items() if value}
        path = "/formations" if page <= 1 else "/formations/page/%s" % page
        return path + ("?" + urlencode(args) if args else "")

    def _card(self, row):
        env = request.env
        formats = self._formats(row)
        session = row.get("next_session")
        next_label = ""
        if session:
            local = fields.Datetime.context_timestamp(
                env.user.with_context(tz=session["timezone"]), session["start_at"]
            )
            next_label = format_date(env, local.date(), date_format="d MMM y")
            if session.get("location"):
                next_label += " · " + session["location"]
        price = row.get("session_price") or (row.get("autonomous") or {}).get("price")
        days = row.get("duration_days") or 0.0
        return {
            **self._linked(row),
            "formats": formats,
            "next_label": next_label,
            "price_label": price["label"] if price else "",
            "price_per_participant": bool(row.get("session_price")),
            "duration_label": formatLang(env, days, digits=0 if float(days).is_integer() else 2) if days else "",
            "duration_plural": days >= 2,
        }

    @http.route(
        ["/formations", "/formations/page/<int:page>"], type="http", auth="public", website=True, methods=["GET"]
    )
    def catalogue(self, search="", category="", mode="", page=1, **kwargs):
        all_rows = self._rows()
        published_count = len(all_rows)
        rows = all_rows
        if search:
            needle = search.casefold()
            rows = [
                row
                for row in rows
                if needle
                in " ".join(
                    [row["name"], row["presentation"], row["objectives"]]
                    + [tag["label"] for tag in row["tags"]]
                    + [offer["title"] for offer in row["offers"]]
                ).casefold()
            ]
        facets = {
            "category": category,
            "mode": mode,
            "format": kwargs.get("format") if kwargs.get("format") in ("inter", "intra", "autonomous") else "",
            "level": kwargs.get("level") if kwargs.get("level") in dict(self._levels()) else "",
            "duration": kwargs.get("duration") if kwargs.get("duration") in self.DURATIONS else "",
            "certifying": "1" if kwargs.get("certifying") == "1" else "",
            "soon": "1" if kwargs.get("soon") == "1" else "",
            "remote": "1" if kwargs.get("remote") == "1" else "",
        }
        sort = kwargs.get("sort") if kwargs.get("sort") in self.SORTS else "relevance"
        options = {
            **self._catalogue_options(**kwargs),
            "search": search,
            **facets,
            "sort": "" if sort == "relevance" else sort,
        }
        matched = [row for row in rows if self._facet_match(row, facets)]
        if sort == "next":
            far = fields.Datetime.now() + relativedelta(years=100)
            matched.sort(key=lambda row: row["next_session"]["start_at"] if row.get("next_session") else far)
        elif sort == "price":
            matched.sort(key=lambda row: (self._min_price(row) is None, self._min_price(row) or 0.0))
        elif sort == "duration":
            matched.sort(key=lambda row: (not row.get("duration_days"), row.get("duration_days") or 0.0))
        elif sort == "new":
            matched.sort(key=lambda row: str(row.get("published_at") or ""), reverse=True)
        pager = portal_pager(
            url="/formations",
            total=len(matched),
            page=page,
            step=CARDS_PER_PAGE,
            url_args={key: value for key, value in options.items() if value},
        )
        start = pager["offset"]

        def facet(key, choices):
            # Each choice counts the courses it would show with the other facets kept.
            others = [row for row in rows if self._facet_match(row, facets, skip=key)]
            items = []
            for value, label in choices:
                count = sum(1 for row in others if self._facet_match(row, {key: value}))
                if count or facets[key] == value:
                    selected = facets[key] == value
                    items.append(
                        {
                            "label": label,
                            "count": count,
                            "selected": selected,
                            "url": self._catalogue_url(options, **{key: "" if selected else value}),
                        }
                    )
            return items

        categories = sorted(
            {(row["category_id"], row["category"]) for row in all_rows if row["category_id"]}, key=lambda c: c[1]
        )
        groups = [
            ("Domaine", facet("category", [(str(cid), name) for cid, name in categories])),
            ("Niveau", facet("level", self._levels())),
            (
                "Durée",
                facet(
                    "duration", [("short", "1 jour ou moins"), ("medium", "2 à 3 jours"), ("long", "4 jours et plus")]
                ),
            ),
            (
                "Autres critères",
                facet("certifying", [("1", "Certifiante")])
                + facet("soon", [("1", "Session dans les 3 prochains mois")])
                + facet("remote", [("1", "Distanciel possible")]),
            ),
        ]
        labels = {
            **{str(cid): name for cid, name in categories},
            **dict(self._levels()),
            "short": "1 jour ou moins",
            "medium": "2 à 3 jours",
            "long": "4 jours et plus",
        }
        flag_labels = {
            "certifying": "Certifiante",
            "soon": "Session dans les 3 prochains mois",
            "remote": "Distanciel possible",
        }
        mode_labels = {"onsite": "Présentiel", "remote": "Distanciel", "blended": "Mixte", "autonomous": "Autonome"}
        active = [
            {
                "label": flag_labels.get(key)
                or (mode_labels.get(value) if key == "mode" else labels.get(value, value)),
                "url": self._catalogue_url(options, **{key: ""}),
            }
            for key, value in facets.items()
            if value and key != "format"
        ]
        format_counts = {
            key: sum(1 for row in rows if self._facet_match(row, {**facets, "format": key}))
            for key in ("inter", "intra", "autonomous")
        }
        formats = [
            {
                "key": "",
                "label": "Toutes les formations",
                "hint": "",
                "count": sum(1 for row in rows if self._facet_match(row, facets, skip="format")),
            },
            {
                "key": "inter",
                "label": "Inter-entreprises",
                "hint": "Sessions à date fixe",
                "count": format_counts["inter"],
            },
            {"key": "intra", "label": "Intra-entreprise", "hint": "Pour votre équipe", "count": format_counts["intra"]},
            {
                "key": "autonomous",
                "label": "En autonomie",
                "hint": "eLearning à votre rythme",
                "count": format_counts["autonomous"],
            },
        ]
        for item in formats:
            item["selected"] = facets["format"] == item["key"]
            item["url"] = self._catalogue_url(options, format=item["key"])
        sorts = [
            {
                "key": key,
                "label": label,
                "selected": sort == key,
                "url": self._catalogue_url(options, sort="" if key == "relevance" else key),
            }
            for key, label in (
                ("relevance", "Pertinence"),
                ("next", "Prochaine session"),
                ("price", "Prix"),
                ("duration", "Durée"),
                ("new", "Nouveautés"),
            )
        ]
        company = request.env.website.company_id if request.env.website else request.env.company
        suggestions = [
            line.strip() for line in (company.training_catalogue_suggestions or "").splitlines() if line.strip()
        ]
        return request.render(
            "training_catalog.public_catalogue",
            {
                **options,
                "courses": [self._card(row) for row in matched[start : start + CARDS_PER_PAGE]],
                "categories": categories,
                "pager": pager,
                "published_count": published_count,
                "result_count": len(matched),
                "facet_groups": [(title, items) for title, items in groups if items],
                "active_facets": active,
                "clear_url": self._catalogue_url(
                    {key: value for key, value in options.items() if key not in facets and key != "search"}
                ),
                "formats": formats,
                "sorts": sorts,
                "current_sort": sort,
                "suggestions": [
                    {"label": label, "url": self._catalogue_url({**self._catalogue_options(**kwargs), "search": label})}
                    for label in suggestions[:8]
                ],
                # A new search keeps the chosen format and order; the journey context has its own field.
                "hidden_options": {key: options[key] for key in ("format", "sort") if options.get(key)},
            },
        )

    @staticmethod
    def _levels():
        course = request.env["training.course"]
        return list(course._fields["public_level"]._description_selection(request.env))

    # Shared wording of the format comparison; each value describes how the course is organised.
    COMPARISON = (
        (
            "Pour qui",
            {
                "inter": "Participants de plusieurs entreprises",
                "intra": "Votre équipe",
                "autonomous": "Chaque apprenant, individuellement",
            },
        ),
        ("Dates", {"inter": "Sessions planifiées", "intra": "À convenir avec vous", "autonomous": "À votre rythme"}),
        (
            "Lieu",
            {
                "inter": "Lieu de la session ou à distance",
                "intra": "Vos locaux ou à distance",
                "autonomous": "En ligne",
            },
        ),
        ("Accompagnement", {"inter": "Avec formateur", "intra": "Avec formateur", "autonomous": "Parcours en ligne"}),
    )

    def _course_values(self, row, published, **kwargs):
        """Page values every application may complete before the page renders."""
        env = request.env
        card = self._card(row)
        formats = dict(card["formats"])
        # A course led by a trainer can be followed in an inter-company session, even
        # before dates are published: the tab then offers the new date alert.
        formats["inter"] = formats["inter"] or bool(row.get("live"))
        tabs = [key for key in ("inter", "intra", "autonomous") if formats[key]]
        active = kwargs.get("format") if kwargs.get("format") in tabs else (tabs[0] if tabs else "")
        presentation = (row["presentation"] or "").strip()
        paragraphs = [part.strip() for part in presentation.replace("\r\n", "\n").split("\n\n") if part.strip()]
        autonomous = row.get("autonomous") or {}
        session_price = row.get("session_price")
        duration = card["duration_label"] and "%s %s" % (
            card["duration_label"],
            "jours" if card["duration_plural"] else "jour",
        )
        autonomous_hours = autonomous.get("hours")
        prices = {
            "inter": "%s HT par participant" % session_price["label"] if session_price else "Sur devis",
            "intra": "Sur devis",
            "autonomous": "%s HT" % autonomous["price"]["label"] if autonomous.get("price") else "Sur devis",
        }
        durations = {
            "inter": duration,
            "intra": duration,
            "autonomous": "%s h"
            % formatLang(env, autonomous_hours, digits=0 if float(autonomous_hours).is_integer() else 1)
            if autonomous_hours
            else "",
        }
        registrations = {
            "inter": "Inscription à une session",
            "intra": "Demande de devis",
            "autonomous": "Achat en ligne" if autonomous.get("price") else "Sur demande",
        }
        comparison = [(label, [values[key] for key in tabs]) for label, values in self.COMPARISON]
        # The place follows the possible modes declared by the version led by a trainer.
        live_modes = set(row.get("live_modes") or [])
        places = {
            frozenset({"onsite"}): {"inter": "Lieu de la session", "intra": "Vos locaux"},
            frozenset({"remote"}): {"inter": "À distance", "intra": "À distance"},
        }.get(frozenset(live_modes), {})
        comparison = [
            (label, [places.get(key, value) for key, value in zip(tabs, values, strict=True)])
            if label == "Lieu"
            else (label, values)
            for label, values in comparison
        ]
        comparison += [
            ("Durée", [durations[key] or "—" for key in tabs]),
            ("Tarif", [prices[key] for key in tabs]),
            ("Inscription", [registrations[key] for key in tabs]),
        ]
        url = request.httprequest.url_root.rstrip("/") + card["url"]
        company = env.website.company_id if env.website else env.company
        schema = StructuredData(
            {
                "@context": "https://schema.org",
                "@type": "Course",
                "name": row["name"],
                "description": paragraphs[0] if paragraphs else row["name"],
                "url": url,
                "provider": {"@type": "Organization", "name": company.name, "url": request.httprequest.url_root},
            }
        )
        if published and published.public_reference:
            schema["courseCode"] = published.public_reference
        if row.get("level"):
            schema["educationalLevel"] = row["level"]
        if session_price and session_price.get("currency"):
            schema["offers"] = [
                {
                    "@type": "Offer",
                    "category": FORMAT_LABELS["inter"],
                    "price": session_price["amount"],
                    "priceCurrency": session_price["currency"],
                }
            ]
        return {
            "course": card,
            "formats": formats,
            "tabs": [{"key": key, "label": FORMAT_LABELS[key], "price": prices[key]} for key in tabs],
            "active_format": active,
            "tagline": paragraphs[0] if paragraphs else "",
            "presentation_more": "\n\n".join(paragraphs[1:]),
            "duration_label": duration,
            "autonomous_duration": durations["autonomous"],
            "autonomous_offers": [offer for offer in card["offers"] if offer["mode"] == "autonomous"],
            "comparison": comparison if len(tabs) > 1 else [],
            "comparison_heads": [FORMAT_LABELS[key] for key in tabs],
            "mobile_price": session_price["label"]
            if session_price
            else (autonomous.get("price") or {}).get("label", ""),
            "mobile_price_per_participant": bool(session_price),
            "related": [
                {**other, "url": self._course_path(other["id"], other["name"])} for other in row.get("related") or []
            ],
            "course_schema": schema,
            # Completed by the programme adapter: published version details.
            "version_details": False,
            "audience_sections": [],
            "modality_sections": [],
            "programme_pdf_url": False,
            "publications_url": False,
            "sessions_url": False,
            "alert_url": False,
        }

    @http.route(
        ["/formations/catalogue/<int:course_id>", "/formations/catalogue/<string:slug>-<int:course_id>"],
        type="http",
        auth="public",
        website=True,
        methods=["GET"],
    )
    def course(self, course_id, slug=None, **kwargs):
        # A catalogue editor may preview an unpublished course of the website operator.
        preview = kwargs.get("preview") == "1" and request.env.user.has_group("training_catalog.group_catalog_editor")
        if preview:
            request.update_context(training_catalogue_preview=(course_id,))
        row = next((row for row in self._rows() if row["id"] == course_id), None)
        if not row:
            raise request.not_found()
        canonical = request.env["ir.http"]._slug((row["id"], row["name"]))
        # One public address per course: the bare identifier and former names redirect permanently.
        if request.httprequest.method == "GET" and canonical != (f"{slug}-{course_id}" if slug else str(course_id)):
            query = request.httprequest.query_string.decode()
            return request.redirect(
                self._course_path(row["id"], row["name"]) + ("?" + query if query else ""), code=301
            )
        courses = request.env["training.course"]
        company = request.env.website.company_id if request.env.website else request.env.company
        published = courses._published_catalogue_course(company, course_id)
        unpublished = preview and not published
        if unpublished:
            published = courses.sudo().search(
                [("id", "=", course_id), ("company_id", "=", company.id), ("active", "=", True)], limit=1
            )
        programme = published.public_programme if published else False
        values = self._course_values(row, published, **kwargs)
        values["preview_unpublished"] = unpublished
        url = values["course_schema"]["url"]
        response = request.render(
            "training_catalog.public_course",
            {
                **values,
                "general_presentation_published": bool(published) and not unpublished,
                "public_programme": Markup(programme) if not is_html_empty(programme) else "",
                "public_reference": published.public_reference if published else False,
                "public_logo": published.public_logo if published else False,
                "public_reviews": published._public_reviews() if published else [],
                "review_status": published._course_review_status(request.env.user) if published else False,
                "review_error": False,
                "review_values": {},
                "review_route": f"/formations/catalogue/{course_id}/avis",
                "course_share": {
                    "url": url,
                    "title": request.env._("Share this course"),
                    "copyText": request.env._("Copy link"),
                    "copied": request.env._("Link copied"),
                    "email": "mailto:?" + urlencode({"subject": row["name"], "body": url}, quote_via=quote),
                    "whatsapp": "https://wa.me/?" + urlencode({"text": f"{row['name']}\n{url}"}),
                },
            },
        )

        if not request.env.user._is_public():
            response.headers["Cache-Control"] = "private, no-store"
            response.headers.add("Vary", "Cookie")
        return response

    @http.route("/formations/catalogue/<int:course_id>/avis", type="http", auth="user", website=True, methods=["POST"])
    def course_review(self, course_id, score="", feedback="", consent="", **kwargs):
        website = request.env.website
        course = request.env["training.course"]._published_catalogue_course(
            website.company_id if website else request.env.company, course_id
        )
        if not course:
            raise request.not_found()
        try:
            course._submit_course_review(request.env.user, score, feedback, consent)
        except AccessError:
            raise request.not_found() from None
        except ValidationError as error:
            response = self.course(course_id, **kwargs)
            response.qcontext.update(
                review_error=str(error),
                review_values={"score": score, "feedback": feedback[:2000]},
            )
            response.status_code = 422
            return response
        return request.redirect(f"/formations/catalogue/{course_id}#training_course_reviews", code=303)
