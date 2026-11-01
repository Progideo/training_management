# Manuel utilisateur HTML

Ouvrir [html/index.html](html/index.html) après téléchargement du dépôt. GitHub
affiche le code HTML ; il ne rend pas le manuel comme un site. Aucune publication
GitHub Pages ni modification d'hébergement n'est nécessaire pour le lire localement.

Le manuel couvre administration, coordination, ventes/facturation, participants,
formateurs/tuteurs/évaluateurs, représentants clients, qualité, supervision et
modération. Les procédures et règles sont dans `source/*.rst` ; les captures
récentes, fictives et réalistes dans `source/images/`. La version du code et la
traçabilité sont indiquées dans le chapitre Références.

## Générer

Depuis la racine du dépôt, avec Python 3.9 ou supérieur :

```sh
python3 -m venv .venv-user-docs
.venv-user-docs/bin/python -m pip install -r docs/user/requirements.txt
.venv-user-docs/bin/sphinx-build -b html -W --keep-going -E -a -d /tmp/tm-user-docs-doctrees docs/user/source docs/user/html
```

Ne pas versionner l'environnement virtuel, les fichiers `.doctrees`, les sessions
de navigateur ou les comptes/mots de passe de démonstration. Le HTML généré est
versionné pour être consultable sans installation. Après suppression ou renommage
d'une page, retirer aussi son ancien HTML avant de régénérer.

## Vérifier et entretenir

1. Relire le changement fonctionnel et les vues/traductions du code de référence.
2. Modifier le chapitre concerné ; conserver les distinctions entre vente,
   admission, accès, progression, présence et décision qualité.
3. Refaire les captures affectées sur des données synthétiques du code courant,
   avec des profils restreints et sans transport réel de courriels.
4. Vérifier chaque image (données fictives, absence de secret ou de lien privé
   dans le contenu), puis actualiser `screenshots.json` et ses empreintes.
5. Générer avec les avertissements bloquants ; ouvrir l'accueil, la navigation,
   la recherche, les figures et une page longue sur ordinateur et mobile.
6. Mettre à jour les sources **et** le HTML dans la même PR. Les résultats de
   vérification restent dans la PR, les règles durables dans le manuel.

Le rendu s'inspire des conventions de la documentation Odoo ; il n'utilise pas
sa marque graphique ou un logo officiel pour faire passer le manuel pour une
publication Odoo. Sphinx est sous BSD-2-Clause ; sphinx-rtd-theme sous MIT.
Les ressources distribuées avec le HTML gardent leurs notices ; voir `NOTICE.md`.
