"""Synchronise uniquement les issues réalisées avec le Project du module.

SPDX-License-Identifier: LGPL-3.0-only
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request


REPOSITORY = "Progideo/training_management"
PROJECT_NUMBER = 1
STATUS_FIELD = "Status"
DONE = "Terminé"


class APIError(RuntimeError):
    """Erreur API sans contenu de réponse ni identifiants secrets."""


class GitHub:
    def __init__(self, token):
        self.token = token

    def request(self, path, payload=None):
        request = urllib.request.Request(
            "https://api.github.com/" + path,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise APIError(f"GitHub a répondu HTTP {error.code}.") from None
        except (urllib.error.URLError, TimeoutError, ValueError):
            raise APIError("Réponse GitHub inaccessible ou invalide.") from None

    def graphql(self, query, variables):
        result = self.request("graphql", {"query": query, "variables": variables})
        if result.get("errors") or not result.get("data"):
            raise APIError("Échec GraphQL : vérifier les permissions et la configuration.")
        return result["data"]

    def issue(self, number):
        return self.request(f"repos/{REPOSITORY}/issues/{number}")

    def target(self):
        cursor = None
        while True:
            data = self.graphql("""
              query($cursor: String) {
                organization(login: "Progideo") {
                  projectV2(number: 1) {
                    id
                    fields(first: 100, after: $cursor) {
                      nodes {
                        ... on ProjectV2SingleSelectField {
                          id name options { id name }
                        }
                      }
                      pageInfo { hasNextPage endCursor }
                    }
                  }
                }
              }
            """, {"cursor": cursor})
            project = (data.get("organization") or {}).get("projectV2")
            if not project:
                raise APIError("Project nº 1 inaccessible.")
            fields = project["fields"]
            for field in fields["nodes"]:
                if field.get("name") == STATUS_FIELD:
                    options = [o for o in field["options"] if o["name"] == DONE]
                    if len(options) != 1:
                        raise APIError("Option Terminé absente ou ambiguë.")
                    return project["id"], field["id"], options[0]["id"]
            if not fields["pageInfo"]["hasNextPage"]:
                raise APIError("Champ Status introuvable.")
            cursor = fields["pageInfo"]["endCursor"]

    def item(self, number, project_id):
        cursor = None
        while True:
            data = self.graphql("""
              query($number: Int!, $cursor: String) {
                repository(owner: "Progideo", name: "training_management") {
                  issue(number: $number) {
                    projectItems(first: 100, after: $cursor, includeArchived: true) {
                      nodes {
                        id project { id }
                        fieldValueByName(name: "Status") {
                          ... on ProjectV2ItemFieldSingleSelectValue {
                            optionId
                          }
                        }
                      }
                      pageInfo { hasNextPage endCursor }
                    }
                  }
                }
              }
            """, {"number": number, "cursor": cursor})
            issue = (data.get("repository") or {}).get("issue")
            if not issue:
                raise APIError("Issue inaccessible dans le dépôt attendu.")
            items = issue["projectItems"]
            for item in items["nodes"]:
                if item["project"]["id"] == project_id:
                    return item
            if not items["pageInfo"]["hasNextPage"]:
                return None
            cursor = items["pageInfo"]["endCursor"]

    def set_done(self, project_id, item_id, field_id, option_id):
        self.graphql("""
          mutation($project: ID!, $item: ID!, $field: ID!, $option: String!) {
            updateProjectV2ItemFieldValue(input: {
              projectId: $project, itemId: $item, fieldId: $field,
              value: {singleSelectOptionId: $option}
            }) { projectV2Item { id } }
          }
        """, {"project": project_id, "item": item_id,
              "field": field_id, "option": option_id})


def completed(issue):
    return (not issue.get("pull_request") and issue.get("state") == "closed"
            and issue.get("state_reason") == "completed")


def synchronize(api, number, *, dry_run=True, allow_write=False, sleep=time.sleep):
    if not completed(api.issue(number)):
        return "ignored: issue ouverte, abandonnée, doublon ou motif non reconnu"
    if not dry_run and not allow_write:
        raise RuntimeError("Écriture désactivée : PROJECT_AUTOMATION_ENABLED doit valoir true.")
    project, field, option = api.target()
    for attempt in range(6):
        item = api.item(number, project)
        if item:
            break
        if not completed(api.issue(number)):
            return "ignored: l’issue n’est plus réalisée"
        if attempt < 5:
            sleep(10)
    else:
        raise RuntimeError("Carte absente après 6 recherches ; vérifier l’ajout automatique puis relancer.")
    # Relire après l’attente et juste avant l’écriture : l’événement peut être ancien.
    if not completed(api.issue(number)):
        return "ignored: l’issue n’est plus réalisée"
    if (item.get("fieldValueByName") or {}).get("optionId") == option:
        return "unchanged: déjà Terminé"
    if dry_run:
        return f"dry-run: l’issue #{number} passerait à Terminé dans le Project nº {PROJECT_NUMBER}"
    api.set_done(project, item["id"], field, option)
    verified = api.item(number, project)
    if not verified or (verified.get("fieldValueByName") or {}).get("optionId") != option:
        raise RuntimeError("Statut final non confirmé ; vérifier le Project avant de relancer.")
    return f"updated: issue #{number} passée à Terminé"


def main():
    number = os.environ.get("ISSUE_NUMBER", "")
    if not number.isascii() or not number.isdecimal() or int(number) < 1:
        raise RuntimeError("ISSUE_NUMBER doit être un entier positif.")
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("Jeton GitHub App absent.")
    result = synchronize(
        GitHub(token), int(number),
        dry_run=os.environ.get("DRY_RUN", "true") != "false",
        allow_write=os.environ.get("PROJECT_AUTOMATION_ENABLED") == "true",
    )
    print(result)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write("### Synchronisation du Project\n\n" + result + "\n")


if __name__ == "__main__":
    try:
        main()
    except (APIError, RuntimeError) as error:
        print(f"Erreur : {error}", file=sys.stderr)
        sys.exit(1)
