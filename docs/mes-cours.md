# Page « Mes cours »

Décision du 28 novembre 2026 : l'espace formation devient une page dédiée,
séparée de « Mon compte ».

## Règles

- **« Mes cours »** (`/my/trainings`) regroupe, en lignes pleine largeur :
  « À faire maintenant », « Mes formations avec formateur », « J'anime »,
  « Mon entreprise », et « Mes cours en ligne » fourni par un module autonome
  (eLearning) via le modèle commun `training.my.courses` du catalogue, sans
  dépendance à Training Management. Cinq lignes au plus par bloc ; « Toutes… » déplie ou
  renvoie à la liste complète. Les autres pages restent accessibles en bas
  (« Autres pages »), par les points d'extension existants.
- **« À faire maintenant »** : présences à signer (demi-journées commencées,
  sans déclaration), présences signées à contrôler (formateur, 30 derniers jours),
  évaluations ouvertes à remettre, évaluations remises à valider, plans de mise
  en pratique prévus. Chaque action renvoie à la page qui l'autorise. Un module
  ajoute ses actions en surchargeant `_courses_todo` du contrôleur participant.
- **Menu principal** : entrée « Mes cours » ajoutée une fois par site (installation
  ou migration 20.0.3.9.0), affichée seulement à une personne connectée ayant un
  cours (`training.portal.navigation._has_courses`).
- **Après connexion** : un utilisateur portail ayant un cours arrive sur « Mes cours » ;
  les autres gardent le comportement d'Odoo. Les utilisateurs internes vont au back-office.
- **« Mon compte »** reste la page standard d'Odoo. Les tuiles « Mes cours »,
  « Ma signature », « Alertes de nouvelles dates » et, avec la gamification,
  « Mes points et badges » y sont des `portal.entry`, affichées selon les compteurs natifs.

## Recette courte

1. Apprenant avec une séance passée non signée : `/my/trainings` montre la
   formation et « Signer » ; après signature, l'action passe au formateur.
2. Personne sans cours : pas d'entrée « Mes cours » au menu ; arrivée sur `/my`.
3. `/my` : tuiles formation présentes seulement pour les personnes concernées.

## Limites

- Un site créé après l'installation ne reçoit pas l'entrée de menu : l'ajouter
  dans l'éditeur (URL `/my/trainings`).
- Questionnaires de satisfaction et examens blancs : actions à raccorder par
  leurs modules ; cours eLearning : à fournir par `training_elearning`.
