# P10 — diagnostic d’orientation avant achat

Référence : [#33](https://github.com/Progideo/training_management/issues/33),
chapitre 21 de la spécification (COM01, ORG01).

## Couverture et choix

Dans Community `20.0-20261015` (digest de la [CI](ci.md)), Surveys fournit
`survey.survey`, les questions à choix unique et leurs réponses proposées,
ainsi que leur éditeur natif. `_create_answer` crée un `survey.user_input` ;
son parcours standard conserve donc une réponse dès le démarrage. Il ne fournit
pas la recommandation métier niveau/formation/parcours expliquée attendue ici.
L’extension de l’addon Surveys réutilise ses définitions, avec une projection
Portal/QWeb et un calcul sans tentative persistée. Website reste facultatif.

Le mini-quiz [P04](p03-p04-public-catalogue.md) reste une démonstration corrigée,
sans orientation ; les examens et évaluations restent pédagogiques. Aucun
nouveau référentiel de formation, parcours, compte ou progression n’est créé.
Les cibles réutilisent les versions de programme et les [parcours P09](p09-learning-paths.md).
Le contact réutilise la [demande P02](p01-p02-guided-requests.md) si Ventes est
installé, sans y transférer les réponses ; sinon le contact public du diagnostic
permet l’échange humain.

## Parcours et règles

Depuis le catalogue, le visiteur choisit un diagnostic facultatif et répond sur
une page. Il peut consulter directement le catalogue ou demander conseil avant
toute réponse. Le résultat affiche la cible, l’explication du coordinateur et
les réponses déterminantes. Le questionnaire reste disponible pour recommencer.

Le coordinateur prépare des questions textuelles à choix unique dans l’éditeur
Surveys simplifié. « Définir les recommandations » enregistre les questions et
leurs choix avant leur sélection dans les règles. Les réglages d’examen, images,
commentaires et génération de pistes ne sont pas proposés dans cette vue.
Il prépare ensuite les règles : toutes les réponses sélectionnées dans une règle
sont nécessaires, avec une réponse par question pour décrire un profil cohérent ;
chaque règle vise exactement un niveau, une version de
formation ou un parcours. Toutes les questions doivent être renseignées.
Une seule règle doit correspondre. Réponses manquantes, paramètres invalides,
absence de correspondance, règles concurrentes ou cible retirée renvoient vers
un conseil humain, sans classement arbitraire ni score trompeur.

Seules les formations publiées et explicitement publiques de la même société
peuvent être recommandées. Un parcours doit être actif, validé et composé
uniquement de telles formations ; le résultat donne son nom et les fiches de ses
formations, sans exposer inscriptions, prérequis privés ni participants.
Ces conditions sont revérifiées au calcul. Le diagnostic publié est figé ;
sa duplication recrée questions et règles en brouillon. « Ouvrir le diagnostic »
permet de vérifier la page publique. L’archivage le retire.

Le diagnostic ne vaut ni positionnement pédagogique, ni validation des
prérequis, ni admission, ni ouverture d’accès, ni promesse de résultat.
Aucune commande, inscription, équivalence ou progression n’en découle.

## Données et droits

Finalité : afficher une aide au choix avant achat. Durée de conservation des
réponses : **nulle**. Les réponses transitent par POST avec CSRF, uniquement
pendant la requête ; aucune réponse ni résultat n’est enregistré dans l’ORM,
la session, les messages ou la demande commerciale. Les pages portent
`Cache-Control: no-store` ; le résultat n’est pas placé dans une URL.
Les routes natives Surveys et la création de tentatives sont fermées pour ces
questionnaires, y compris les invitations et tentatives de test.
Ne pas configurer de journalisation des corps POST ou d’outil de collecte des
formulaires sur ces pages lors de l’exploitation.

Les définitions et règles sont réservées aux coordinateurs de la société.
Le public et le portail n’ont aucun accès ORM supplémentaire. La publication
accorde uniquement la projection publique bornée à la société du site Website,
ou à la société courante sans Website. Les réponses ne sont accessibles ni
à l’employeur, ni à un autre participant, ni à un conseiller.
La société des règles est imposée par le diagnostic, y compris pour les appels
ORM et valeurs par défaut. Les questions et choix existants ne peuvent pas être
déplacés vers un diagnostic : les dupliquer permet de réutiliser leur définition
sans importer de réponses enregistrées, même lors d’accès concurrents. Les
historiques ordinaires restent inchangés.

## Recette courte

1. Dans Formations → Diagnostics d’orientation, créer deux questions textuelles à
   choix unique et un contact public. Cliquer « Définir les recommandations »,
   puis ajouter une règle vers un niveau avec explication. Publier ; vérifier le lien depuis le catalogue, sans obligation de compte.
2. Répondre complètement : lire la cible, l’explication et les critères.
   Vérifier le contact humain et l’absence de prétention d’admission.
3. Omettre une réponse, choisir une combinaison sans règle, puis configurer deux
   règles concurrentes dans une copie : obtenir systématiquement le conseil.
4. Recommander une formation publique, puis un parcours validé aux étapes
   publiques. Retirer une formation : aucune recommandation indisponible.
5. Tester brouillon, autre société, lien natif Surveys et paramètres forgés :
   refus ou conseil, sans fuite. Essayer de modifier le diagnostic publié,
   puis le dupliquer : refus de modification et nouvelle copie modifiable.
6. Répéter la soumission ; vérifier l’absence de tentative, réponse enregistrée,
   contact créé, inscription ou progression. Avec Ventes, ouvrir « Demander
   conseil » : le formulaire P02 ne contient aucune réponse du diagnostic.
