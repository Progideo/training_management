# Navigation et compatibilité des thèmes

Références : UX01, ESP01, PRE01–03, SEC01 et PIL01 de la spécification ;
[parcours et demi-journées](review-experience-performance.md).

## Parcours

- Le portail conserve « Mes formations » et les missions cumulées. La fiche
  présente les activités encore disponibles à réaliser, sans modifier leur ordre,
  leurs prérequis ni les critères de complétion. Les retours récents précèdent les
  anciens échanges ; tous restent consultables.
- Les pages métier ont un retour vers cet espace. Le filtre et la page des séances
  sont conservés jusqu’au contrôle des présences. Les séances terminées restent
  accessibles au formateur affecté avant clôture, selon le droit serveur existant.
- La présence distingue déclaration attendue, contrôle attendu, validation
  partielle, validation et invalidation. Une demi-journée future reste indisponible.
  Le constat d’absence demeure possible sans déclaration préalable ; présence,
  contrôle distinct, motifs, durée prévue et anciennes preuves gardent leurs règles.
- Les commandes d’examen se réorganisent sur mobile. Les erreurs ciblent le
  formulaire concerné et les dates affichées nomment le fuseau utilisateur.
  Une échéance locale ambiguë lors d’un changement d’heure est refusée.
- La vue d’ensemble interne ouvre le suivi des missions affectées, ou le catalogue
  pour les profils de lecture/commerciaux sans mission pédagogique. Les opérations
  secondaires d’inscription utilisent le menu Actions natif ; les confirmations,
  autorisations commerciales et ouvertures d’accès restent séparées.
- La qualité retrouve les preuves en premier et la clôture dans Qualité. Les
  définitions pédagogiques sont rangées dans Configuration. Le dossier entreprise
  rappelle le lot et distingue places non affectées et propositions en attente.

## Layouts et thèmes Odoo

Le code exact Community `20.0-20261015` fait hériter `website.layout` de
`portal.frontend_layout`. Les pages publiques utilisent ce dernier pour conserver
le socle sans dépendance Website, tout en recevant le thème si Website est installé.
Elles fournissent un seul `div#wrap` dans le `main` natif. Les pages privées gardent
`portal.portal_layout`. Aucun second `main`, police ou jeu de couleurs imposé.

Les formulaires, cartes, tableaux et boutons utilisent Bootstrap/Odoo. La feuille
SCSS du module se limite au placement des liens et à l’en-tête Portal sur mobile,
sans modifier les variables du thème. Les interactions réutilisent
`web.public.interaction`. Les données et formulaires issus des contrôleurs sont
marqués non éditables : le constructeur de site ne doit pas réécrire une preuve,
un programme publié ou une action privée.

`training_management_website` est un pont optionnel : il s’installe automatiquement
avec le socle et Website et crée un menu `website.menu` vers `/formations` dans le
site natif initial. Ce menu reste modifiable et sa configuration est conservée aux
mises à jour. Les autres sites choisissent leur propre menu via Website ; aucun
menu ni thème existant n’est remplacé. Le socle reste autonome sans ce pont.

La vérification d’attestation utilise `web.layout` et uniquement les CSS du thème.
Le layout complet Website et ses outils de suivi ne reçoivent pas le lien privé
de vérification. Projection publique, refus, en-têtes et anciens PDF sont conservés.

Les [principes officiels de pages Odoo](https://www.odoo.com/documentation/saas-19.3/developer/howtos/website_themes/pages.html)
complètent cette vérification du code exact ; ils ne constituent pas une preuve
indépendante de compatibilité Odoo 20 ou de tous les thèmes tiers.

## Recette courte

1. Installer le socle sans Website, puis les intégrations avec Website. Mettre à
   jour une base existante ; conserver PDF, présences, autorisations et menus modifiés.
2. Comparer participant, formateur, tuteur, entreprise, commercial, qualité,
   superviseur et cumuls. Retirer une mission : lien absent et accès direct refusé.
3. À 320 et 390 px : terminer un examen, déclarer une absence, contrôler une
   présence et revenir à une séance passée. Vérifier clavier, focus et messages.
4. Tester une déclaration manquante, une période future, une décision périmée et
   deux fuseaux avec changement d’heure, sans retrait d’un contrôle serveur.
5. Changer la palette native du thème : boutons, textes et formulaires suivent
   le thème ; un seul repère principal, aucun défilement horizontal global.
   Vérifier aussi demandes, sessions publiques, avis et attestations.
6. Avec un outil de suivi fictif configuré, ouvrir la vérification d’attestation :
   styles natifs présents, aucun script de suivi ni lien vers un remplacement.

Les résultats d’exécution restent dans la livraison. Le clavier intégral, les
lecteurs d’écran, les appareils réels et chaque thème tiers nécessitent leur recette.
