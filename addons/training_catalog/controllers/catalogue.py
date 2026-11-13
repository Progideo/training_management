"""Public general information, with optional offers supplied by each application."""

from odoo import http
from odoo.http import request


class TrainingCatalogue(http.Controller):
    @staticmethod
    def _rows():
        # The website selects its operating company; never take one from a URL.
        website = request.env.website
        return request.env["training.course"]._catalogue_rows(website.company_id if website else request.env.company)

    @http.route("/formations", type="http", auth="public", website=True, methods=["GET"])
    def catalogue(self, search="", category="", mode="", **kwargs):
        rows = self._rows()
        categories = sorted({(row["category_id"], row["category"]) for row in rows if row["category_id"]})
        if search:
            needle = search.casefold()
            rows = [
                row
                for row in rows
                if needle
                in " ".join(
                    [row["name"], row["presentation"], row["objectives"]] + [offer["title"] for offer in row["offers"]]
                ).casefold()
            ]
        if category:
            rows = [row for row in rows if str(row["category_id"]) == category]
        if mode:
            rows = [row for row in rows if any(offer["mode"] == mode for offer in row["offers"])]
        return request.render(
            "training_catalog.public_catalogue",
            {"courses": rows, "categories": categories, "search": search, "category": category, "mode": mode},
        )

    @http.route("/formations/catalogue/<int:course_id>", type="http", auth="public", website=True, methods=["GET"])
    def course(self, course_id, **kwargs):
        row = next((row for row in self._rows() if row["id"] == course_id), None)
        if not row:
            raise request.not_found()
        return request.render("training_catalog.public_course", {"course": row})
