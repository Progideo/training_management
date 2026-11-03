# Catalogue commun et séparation des applications

Référence : cadrage consolidé v1 du 3 novembre 2026, 41 décisions validées,
notamment D20/D21/D28/D30/D36. [Issue J1 #123](https://github.com/Progideo/training_management/issues/123).
Le document conservé dans le projet porte l'empreinte indiquée dans la PR.
Les décisions récentes prévalent sur la spécification historique ; aucune
acceptation contractuelle de l'estimation analytique n'est déduite du démarrage.

## Première tranche

`training_catalog` possède `training.course` et `training.category` : identité,
société, catégorie, présentation et objectifs généraux. Aucune présence,
inscription, progression, vente ou question d'examen. Website est une dépendance
validée ; Ventes et Survey restent absents du socle.

TM hérite de `training.course` pour les programmes et leurs protections historiques.
Les tables et noms de modèles sont conservés, sans duplication ni conversion métier.
Les groupes TM historiques restent valides. Les groupes du catalogue n'accordent
aucune permission sur les inscriptions, résultats ou attestations TM. Le lecteur
lit, l'éditeur modifie ; aucun accès ORM public/portail. Les règles serveur limitent
les deux référentiels aux sociétés actives autorisées ; pas de société partagée.
L'interface TM garde son formulaire programme prioritaire ; le socle dispose d'un
menu natif propre. L'éditeur catalogue peut modifier la présentation générale.

Cette tranche ne publie pas encore le nouveau catalogue sur le site. Les anciennes
routes publiques TM restent présentes : leur réduction à la présentation générale
(D28), y compris les aperçus/PDF/démonstrations accessibles par lien direct, est un
incrément suivant requis avant qualification de la cible. Les programmes privés,
P10/P14, présences signées et P20 restent dans TM.

Aucune migration de l'ancienne génération en base existante n'est revendiquée.
La recette porte sur installations neuves puis mises à jour de la nouvelle
génération. Aucun ancien addon n'est désinstallé et aucun historique n'est supprimé.

## Contrats des dix addons cibles

| Dépôt | Addon | Dépendances structurantes et frontière |
| --- | --- | --- |
| TM | training_catalog | base, mail, portal, website ; identité et présentation seulement |
| TM | training_mock_exam | training_catalog, survey ; familles/versions et tentatives natives |
| TM | training_interactive | training_catalog ; paquets H5P/SCORM, sans inscription TM ni slide |
| TM | training_management | training_catalog et services actuels ; métier avec formateur |
| TM | training_management_sale | training_management, sale_management, sale_crm |
| TM | training_management_survey | training_management, training_mock_exam ; contexte encadré |
| TM | training_management_interactive | training_management, training_interactive ; droits encadrés |
| eLearning | training_elearning | training_catalog, training_interactive, website_slides |
| eLearning | training_elearning_sale | training_elearning, sale_management ; CRM à confirmer |
| eLearning | training_elearning_survey | training_elearning, training_mock_exam, website_slides_survey |

Cette page décrit l’extraction initiale du catalogue. La [tranche bibliothèque interactive](j1-shared-interactive.md) poursuit les extractions communes. Les autres lignes décrivent la
cible, pas des manifests livrés. Les addons historiques `training_management_website`
et `training_management_elearning` sont des composants à absorber/remplacer,
pas des onzième/douzième addons cibles. `sale_invoice_address_fiscal` est une
extension native existante hors architecture pédagogique ; ne pas la supprimer.
Pas de troisième dépôt ni de dépendance métier croisée. L'autonomie complète
eLearning n'est pas acquise par la seule extraction du catalogue.

## Inventaire et preuves de code

Références de départ : TM `616d2a342540eb7a7dbb8e48d6ecd084bc2fc926` ;
eLearning `main` `2c3db9dee4c3c1bbf6137955a5403f3533f2e117` et correctif
`d7d3b976d07831bca2de3c75d6c159308adf7f0d` (PR #11 ouverte).
L'ancien E00 eLearning, qui impose TM et exclut website_slides, reste historique ;
il devra être amendé dans la PR qui extrait son code. Aucun changement de ce dépôt
n'est nécessaire à la première tranche du catalogue.

Inventaire des manifests au départ (tous déclarés LGPL-3) :

| Addon existant | Dépendances directes au départ |
| --- | --- |
| training_management 20.0.2.11.1 | base, mail, resource, portal, web, base_report_wkhtmltox |
| training_management_sale 20.0.2.5.0 | training_management, sale_management, sale_crm |
| training_management_survey 20.0.2.8.0 | training_management, survey |
| training_management_website 20.0.1.0.0 | training_management, website ; installation automatique |
| sale_invoice_address_fiscal 20.0.1.2.0 | sale_management ; extension hors architecture pédagogique |
| training_management_elearning 20.0.2.2.1 (correctif #11) | training_management, training_management_survey |

Le manifeste eLearning courant est donc déjà plus couplé que la première version
d'E00 : Survey est devenu obligatoire dans cet addon historique. Le nouveau socle
catalogue est le seul addon ajouté par cette tranche ; TM passe à 20.0.3.0.0 et en
dépend. Les manifests des autres composants existants restent inchangés.

Image exacte : `odoo@sha256:61e3c71b0503c5f658e604c3e340bede20b97d05f726179fa006eae50a32fd23`.
Sources Community de cette image, sous `odoo/addons/` :

| Source et point | Constat | Conséquence pour la suite |
| --- | --- | --- |
| website_slides/models/slide_channel_partner.py, `_channel_partner_uniq` | Unique cours/contact | Une édition = un cours ; renouvellement sans seconde progression |
| même fichier, `_recompute_completion` | Nombre de contenus terminés / total ; acquis de cours terminé conservé | La facultativité et les obligations doivent être projetées explicitement |
| website_slides_survey/models/slide_slide.py, `survey_id` | Plusieurs contenus peuvent référencer un questionnaire | Ne pas recopier les examens par offre/mode |
| website_slides_survey/models/survey_user.py, `_check_for_failed_attempt` | Peut retirer une adhésion et notifier après dernier échec | Neutraliser ce flux commercial/certifiant pour les examens illimités |
| survey/controllers/main.py, `survey_submit` | Tolérance ajoutée de 10 secondes au délai global | Ne pas déléguer le délai strict TM au seul contrôleur natif |
| website_slides/controllers/main.py, `_slide_mark_completed`, `slide_set_completed` | Contrôle `can_self_mark_completed` sur les routes natives | Inclure les obligations/prérequis dans les contrôles, tester les liens directs |
| TM survey/models/service.py, `_start` ; models/attempt.py, `_training_one_active` | Recherche/index actif par contact et famille, sans contexte | Ajouter le contexte avant partage entre modes/inscriptions |
| eLearning models/attempt.py, progression.py | Tentatives liées à inscription/usage TM ; projection training.learning.progress | Extraire les lecteurs et réécrire les adaptateurs ; pas de transfert aveugle |

Ces constats de code orientent l'extraction. Le probe natif
`tests/probes/j1_native_contracts.py` vérifie les cardinalités, deux examens,
le questionnaire partagé, deux adhésions séparées, un cours à 50 % après un
seul examen, une nouvelle tentative ORM vide après réussite et l'acquis conservé.
Il force les calculs différés avant de lire la projection. Il ne qualifie ni
les routes cibles, ni les examens facultatifs, ni l'expiration personnalisée.
Le générateur natif `_generate_certification_url` réutilise la dernière tentative :
la possibilité ORM ne suffit donc pas à démontrer le bouton de nouvelle tentative.

Commande reproductible isolée : `python3 tests/ci/run_j1.py` (Docker requis,
image épinglée). Les contrôles font partie de l'orchestration CI existante.
Ils créent leurs propres services ; ils ne ciblent aucune base de recette existante.
Deux examens, facultatif/requis, deux contextes, nouvelle tentative après réussite,
expiration, prérequis par lien direct et projection atomique restent à démontrer
avec les extractions correspondantes. P07/P08 et les délais serveur sont conservés.

## Recette courte

1. Base neuve : installer Catalogue seul. Un éditeur crée catégorie, formation,
   présentation et objectifs ; un lecteur consulte sans modifier.
2. Vérifier qu'un portail/public n'accède pas aux modèles ; un éditeur de société A
   ne lit pas B et ne lie pas une catégorie de B.
3. Base neuve distincte : installer TM. Le coordinateur retrouve formations et
   programmes ; l'éditeur catalogue n'obtient aucun accès aux inscriptions TM.
4. Créer des références fictives, mettre à jour catalogue/TM et vérifier identité,
   textes et relations conservés. Rejouer catalogue, signatures et P20.

J1 complet exigera encore TM seul, eLearning seul et coexistence, puis les preuves
ciblées ci-dessus. Les résultats réels et limites restent dans la PR ; aucune
fusion, bascule ou intervention OVH implicite.
