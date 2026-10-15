# Issues réalisées → Terminé

Cette automatisation concerne uniquement `Progideo/training_management` et le
[Project privé nº 1](https://github.com/orgs/Progideo/projects/1).

## État initial : désactivée

La PR ajoute le workflow sans activer les écritures. Ne pas créer la variable
`PROJECT_AUTOMATION_ENABLED` avec la valeur `true` avant validation humaine.
La fusion de cette PR ne suffit pas à activer les clôtures automatiques.

## Règle

- À chaque événement `issues.closed`, relire l’issue sur GitHub.
- Écrire `Status = Terminé` uniquement si elle est encore fermée avec le motif
  `completed`. Les motifs `not_planned`, `duplicate`, absents ou inconnus sont ignorés.
- Ignorer les pull requests et les issues déjà en `Terminé`.
- Rechercher exclusivement la carte existante du Project nº 1 ; aucune carte créée.
- Si la carte manque, effectuer jusqu’à 6 recherches espacées de 10 secondes.
  L’échec est visible dans Actions ; une relance manuelle est possible.
- Relire l’issue juste avant l’écriture et vérifier le statut après l’écriture.
- Ne modifier ni l’issue, ni les labels, ni les jalons, ni les autres Projects.

La règle native **Item closed** reste désactivée. Les règles natives d’ajout et de
réouverture restent actives. Le passage en **À valider** demeure manuel.

Le motif `completed` reflète le choix de la personne qui clôture l’issue ;
le workflow n’évalue pas lui-même la recette ou la validation fonctionnelle.

## 1. Créer une GitHub App appartenant à Progideo

Dans l’organisation : **Settings → Developer settings → GitHub Apps → New GitHub App**.

- Nom proposé : `Progideo Training Project Bot` (adapter si le nom est déjà pris).
- Homepage URL : `https://github.com/Progideo/training_management`.
- Callback URL : laisser vide ; ne pas activer les fonctions OAuth ou Device Flow.
- Webhook : désactiver **Active**. GitHub Actions reçoit les événements du dépôt.
- Repository permissions : **Issues — Read-only** ; les métadonnées en lecture
  sont accordées automatiquement. Aucune permission d’écriture du code.
- Organization permissions : **Projects — Read and write**.
- Installation autorisée : **Only on this account**.

La permission Projects peut porter sur plusieurs Projects de l’organisation.
Le code et le numéro de Project fixés dans ce dépôt limitent son usage au nº 1.

## 2. Installer l’App

Ouvrir **Install App**, choisir **Progideo**, puis **Only select repositories** et
sélectionner uniquement **training_management**. Vérifier le récapitulatif des
permissions avant de confirmer l’installation.

## 3. Enregistrer l’identifiant et la clé

Dans la fiche de l’App, relever le **Client ID**, puis générer une clé privée
dans **Private keys → Generate a private key**.

Dans le dépôt : **Settings → Secrets and variables → Actions**.

| Type | Nom exact | Valeur |
|---|---|---|
| Variable | `PROJECT_APP_CLIENT_ID` | Client ID de l’App |
| Secret | `PROJECT_APP_PRIVATE_KEY` | Contenu complet du fichier PEM téléchargé |
| Variable | `PROJECT_AUTOMATION_ENABLED` | `false` pendant la configuration |

Saisir la clé directement dans le formulaire sécurisé GitHub, jamais dans une
issue, une PR, le dépôt ou une conversation. Conserver le fichier dans un stockage
sécurisé conformément à vos pratiques. Le jeton d’installation est temporaire et
révoqué par l’action à la fin du job.

## 4. Tests avant activation

Tests locaux, sans réseau et sans secret :

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Après revue et fusion de la PR, le workflow apparaît dans **Actions → Project —
issue réalisée → Run workflow**. Choisir la branche **main**, saisir le numéro
d’une issue existante et conserver **dry_run = true**. Aucun changement de carte
n’est effectué. Les simulations sont permises même si l’activation vaut `false`.

Avec des issues de recette explicitement autorisées et déjà ajoutées au Project :

| État de l’issue | Résultat attendu en simulation |
|---|---|
| Fermée comme réalisée | `dry-run` : passerait à Terminé |
| Fermée comme abandonnée | `ignored` |
| Fermée comme doublon | `ignored` |
| Rouverte | `ignored` |
| Réalisée et déjà Terminé | `unchanged` |

Vérifier les journaux et le résumé de l’exécution. Aucun test réel sur GitHub
n’est effectué par la préparation de la PR. Le test d’écriture et sa répétition
nécessitent une validation d’activation et une issue de recette autorisée.

## 5. Activer après validation humaine

Passer `PROJECT_AUTOMATION_ENABLED` à `true` uniquement après validation. Les
prochaines clôtures déclencheront alors la synchronisation. Pour une première
écriture contrôlée, lancer manuellement le workflow sur une issue de recette
réalisée avec `dry_run = false`, puis le relancer : attendre `updated`, puis
`unchanged`.

Les issues clôturées avant l’activation ne sont pas traitées rétroactivement.
Utiliser une exécution manuelle par numéro si une reprise est souhaitée.

## Arrêt et limites

- Arrêter : remettre `PROJECT_AUTOMATION_ENABLED` à `false`. Cela bloque les
  nouveaux jobs automatiques ; annuler aussi les exécutions déjà en cours.
- Pour restaurer un statut erroné, corriger manuellement la carte après vérification
  de l’historique du Project. Le workflow n’effectue aucune suppression.
- Pour révoquer l’accès, suspendre/désinstaller l’App ou révoquer sa clé privée.
- Une modification du motif seule ne garantit pas un nouvel événement `closed` :
  utiliser la relance manuelle, qui relit toujours l’état actuel.
- GitHub ne fournit pas de transaction atomique entre l’état de l’issue et le
  champ du Project. Une réouverture survenant exactement après la dernière lecture
  peut entrer en concurrence avec l’écriture. Vérifier alors la carte et la règle
  native de réouverture ; la concurrence du workflow ne sérialise que ses propres jobs.
- Une carte absente, un champ renommé, un accès refusé ou une réponse invalide
  provoquent un échec visible. Les droits réels de l’App seront vérifiés en simulation.
- Les actions officielles sont fixées à des SHA ; les mises à jour passent par PR.

## Références

- [Automatiser Projects avec Actions](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/automating-projects-using-actions)
- [Créer une GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app)
- [Action officielle de génération du jeton](https://github.com/actions/create-github-app-token)
