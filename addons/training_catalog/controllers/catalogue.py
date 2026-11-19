"""Public general information, with optional offers supplied by each application."""

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


class TrainingCatalogue(http.Controller):
    @staticmethod
    def _rows():
        # The website selects its operating company; never take one from a URL.
        website = request.env.website
        return request.env["training.course"]._catalogue_rows(website.company_id if website else request.env.company)

    def _catalogue_options(self, **kwargs):
        return {}

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
            "mode": lambda: any(offer["mode"] == facets["mode"] for offer in row["offers"]),
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
            **row,
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

    @http.route("/formations/catalogue/<int:course_id>", type="http", auth="public", website=True, methods=["GET"])
    def course(self, course_id, **kwargs):
        row = next((row for row in self._rows() if row["id"] == course_id), None)
        if not row:
            raise request.not_found()
        courses = request.env["training.course"]
        company = request.env.website.company_id if request.env.website else request.env.company
        published = courses._published_catalogue_course(company, course_id)
        programme = published.public_programme if published else False
        duration = published.live_duration_days if published else 0.0
        formatted_duration = formatLang(request.env, duration, digits=0 if duration.is_integer() else 2)
        url = request.httprequest.url_root.rstrip("/") + f"/formations/catalogue/{course_id}"
        response = request.render(
            "training_catalog.public_course",
            {
                "course": row,
                "general_presentation_published": bool(published),
                "public_programme": Markup(programme) if not is_html_empty(programme) else "",
                "public_reference": published.public_reference if published else False,
                "live_duration": duration,
                "live_duration_label": formatted_duration,
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
