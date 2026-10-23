# S05 Supports pédagogiques privés et espace participant

**Cadrage validé.** Référence : [S05 #15](https://github.com/Progideo/training_management/issues/15), ESP01, PED01–PED02, INS03–INS05, SEC01–SEC02 et UX01 de la [spécification v2](references/Training_Management_Specification_Fonctionnelle_v2.md).

Ce cadrage intègre le préalable technique [S02.1 #50](https://github.com/Progideo/training_management/issues/50).
Réutiliser le portail Odoo, les fichiers natifs et les habilitations existantes.
Ajouter seulement le rattachement pédagogique et les contrôles manquants.
Le préalable #50 est fusionné via [la PR #57](https://github.com/Progideo/training_management/pull/57).

## Références et limites du lot

Base de référence du cadrage : `main` au commit `5819e986a8388b06cc8c315c992a034df5c8022c`,
[PR #56 fusionnée](https://github.com/Progideo/training_management/pull/56).
Le [PDF de programme](catalogue-categories-pdf.md) est déjà conservé et protégé.
S05 doit donner accès au fichier applicable après habilitation, sans le dupliquer,
le régénérer ni modifier son gel. Les [inscriptions et périodes S03](s03-enrollment-access.md)
et le [planning et portail formateur S04](s04-preparation-sessions.md) restent les références métier.

Le [pilotage #3](https://github.com/Progideo/training_management/issues/3) décrit encore S04 en cadrage ;
la fusion et la livraison documentées dans les PR font référence. Les mentions
historiques « base seulement » ne décrivent plus le manifest courant : le socle
dépend déjà de `base, mail, resource, portal, web, base_report_wkhtmltox`.
#50 est clôturée. Sa politique documentaire est la référence technique pour S05 et P05.

L'issue S05 dépasse les seuls supports : elle comprend aussi remises privées,
progression et tutorat de base. Le premier périmètre proposé ci-dessous est
livrable séparément ; il ne permet pas de déclarer #15 terminée.

| Périmètre proposé | Contenu |
| --- | --- |
| Préalable intégré au cadrage — S02.1 #50 | Consolider la politique documentaire et les surcharges S02 ; conserver les comportements commerciaux et comptables ; prouver les accès et les envois avant leur réutilisation par S05. |
| Premier incrément S05 | Espace participant natif, programme applicable existant, agenda S04, supports PDF privés, contrôle courant des droits, conservation des fichiers diffusés. Présentiel, distanciel, mixte et autonome sans séance fictive. |
| Complément nécessaire pour terminer S05 | Activités et critères explicites, dépendances acycliques, remises/corrections privées, aide privée, tuteur, échéances et relances configurables. Aucun report implicite en phase 2. |
| Intégrations ultérieures | Examens S06, émargement S07, attestations S08, évaluations S09 : liens dans le même espace quand disponibles, sans simulation ni boutons inactifs. Portail entreprise P05 et extraits publics P04 restent distincts. |

## Couverture native dans la distribution exacte

Sources de l'image locale `odoo@sha256:61e3c71b0503c5f658e604c3e340bede20b97d05f726179fa006eae50a32fd23`,
racine `/usr/lib/python3/dist-packages/odoo`. `release.py` indique
`20.0-20261015`, provenance Community `49529f034a60e4e9838e08e0a5616e5f2f38c601`.
Les chemins et méthodes ci-dessous constituent des preuves de code, pas une recette HTTP.

| Standard et preuve dans l'image | Capacité démontrée par lecture | Écart et choix proposé |
| --- | --- | --- |
| `addons/base/models/ir_attachment.py`, `_compute_res_access`, `_can_return_content`, `_to_http_stream` | Stockage natif, fichier lié à un parent et à un champ ; accès fondé sur ce parent/champ. Un jeton valide ou `public=True` peut autoriser le contenu. | Garder le stockage. Un fichier privé au sens S05 doit aussi imposer l'identité et les droits métier courants ; le seul booléen public ne suffit pas. |
| `addons/base/models/ir_binary.py`, `_find_record`, `_record_to_stream` | Résolution des fichiers, contrôle de lecture, accès alternatif par jeton de champ limité ; élévation avant le flux dans certains chemins. | Couvrir aussi les jetons de champ et le dernier point de diffusion. Protéger uniquement une route S05 laisserait d'autres chemins natifs à contrôler. |
| `addons/web/controllers/binary.py`, `content_common`, `content_image`, `upload_attachment` | Routes natives contenu/image et dépôt ; téléchargement et prévisualisation. Un jeton passé en URL marque le flux public ; `unique` peut demander un cache long. | Vérifier toutes les URL, variantes de champs et caches. Aucun jeton partageable, cache public ou pièce orpheline accessible pour les supports S05. |
| `addons/portal/controllers/portal.py`, `_document_check_access` ; manifest Portal | Pages et authentification natives ; contrôle ORM avec alternative par jeton, puis objet privilégié. Portal dépend de `auth_signup, base_address_extended, html_editor, http_routing, mail, web`, sans dépendance directe à Website. | Réutiliser comptes, gabarits et navigation. Une route métier authentifiée doit vérifier l'inscription nominative ; le helper seul ne connaît pas S03. Aucun droit ORM général au portail sur les dossiers. |
| `addons/website_slides/models/slide_slide.py`, `binary_content`, `_can_return_content`, `action_mark_completed` ; contrôleur `slide_get_pdf_content` | PDF locaux avec champ binaire natif, aperçu et progression par membre ; les règles du modèle contrôlent le contenu publié. Un contenu non quiz peut être marqué terminé par son membre. | Ne pas assimiler complétion et acquisition. La route PDF lit directement le binaire après résolution du modèle : une intégration eLearning exigerait aussi sa protection, pas seulement celle de `/web/content`. |
| `addons/website_slides/security/ir.access.csv`, modèles `slide.channel`, `slide.channel.partner` | Lecture selon publication, aperçu, visibilité et appartenance/invitation ; inscriptions par contact, progression par cours/contact. | Pas de lien natif aux inscriptions, périodes et autorisations S03 dans ces contrôles. Une appartenance au cours ne prouve pas un droit actuel sur une réalisation. Les groupes Officer/Manager impliquent des droits internes et éditeur Website : ne pas les attribuer aux formateurs externes. |
| `website_slides/models/slide_channel_partner.py`, `_recompute_completion` | Pourcentage à partir des contenus actifs publiés terminés ; appartenance invitée ou déjà terminée non recalculée dans ce chemin. | Historique applicable par inscription, activités facultatives, remises et tutorat S05 ne sont pas démontrés conformes par ce calcul. |
| Manifest `website_slides` ; `website_sale_slides/models/sale_order.py`, `_action_confirm` | eLearning dépend directement de `portal_rating, website, website_mail, website_profile, digest` ; le pont commercial ajoute l'acheteur au cours payé à la confirmation. | Ensemble plus large que les supports privés ; le pont ne remplace jamais l'admission S03. Ne pas installer eLearning ni Website Sale pour ce premier besoin. |

Les manifests Portal et eLearning déclarent LGPL-3, compatible avec le dépôt.
La présence dans l'image ne prouve pas l'installation sur la base dev.
L'hypothèse « invitation eLearning = sécurité S05 » est écartée par la différence
de règles ; aucune vulnérabilité générique d'Odoo n'est déduite de cette étude.

**Architecture recommandée :** extensions ciblées du socle existant, sans nouvel
addon ni application séparée. Un petit modèle métier de support/version et son
affectation représentent le lien absent du standard. Les octets restent dans
`ir.attachment`. Pas de seconde bibliothèque de fichiers, d'authentification ou
de registre d'inscriptions. eLearning reste une option d'intégration à réévaluer
sur un besoin pédagogique démontré, avec son coût de contrôle de toutes les routes.

## Préalable technique S02.1 intégré au cadrage

#50 vise la maintenabilité des protections existantes, avec comportement S02
inchangé. La cible est une politique unique « qui peut voir ou recevoir ce
document », avec des critères propres à chaque catégorie. Une habilitation
commerciale ne devient jamais une habilitation pédagogique.

| Catégorie | Source de la décision à conserver |
| --- | --- |
| Devis et commande | Contacts nommément habilités sur le document, dans le périmètre interne natif Ventes. |
| Facture | Habilitation propre à la facture ; aucune synchronisation nouvelle depuis la commande. |
| Reçu de paiement | Intersection des habilitations des factures rapprochées ; conserver le refus de destinataire externe pour un paiement non affecté ou mêlant formation et autres factures. |
| Pièce jointe ou message commercial | Document d'origine effectivement protégé ; ni jeton, ni destinataire historique, ni abonnement au fil ne remplace l'habilitation courante. |
| Support, remise ou aide S05 | Inscription et affectation pédagogiques selon les règles de cette page ; ces critères seront ajoutés lors de S05, sans dépendance du socle envers Ventes. |

Le code courant comporte déjà des règles globales sur `sale.order` et `account.move`
dans `training_management_sale/security/ir.access.csv`. Il répète aussi les décisions
dans les contrôleurs portail, `ir_binary.py`, `mail_mail.py`, `mail_template.py` et
les assistants d'envoi. `_training_receipt_allowed_partners()` centralise déjà le
calcul des destinataires des reçus. Ces points sont des constats de lecture ;
ils ne prouvent pas qu'une surcharge peut être supprimée sans perte de protection.

Le travail #50 proposé se déroule dans `training_management_sale`, sans nouvel
addon, écran, validation ou liste d'habilitation à saisir :

1. Inventorier chaque méthode surchargée avec son exigence, le chemin natif couvert,
   ses appels à `sudo()` et le test associé. Séparer confidentialité documentaire,
   intégrité comptable et interdiction du paiement en ligne.
2. Centraliser la résolution du document protégé et la décision par opération
   (lecture ou envoi), en conservant les droits natifs et les règles globales.
   Le contrôle d'un destinataire de courriel ne doit pas exiger artificiellement
   un compte portail ; l'accès portail reste authentifié. Un même calcul métier
   peut être réutilisé à plusieurs points de contrôle nécessaires.
3. Faire appeler cette politique par les routes, flux binaires et envois concernés.
   Garder le contrôle au transport et à la reprise : une révocation après mise
   en file doit encore empêcher l'envoi. Ne pas confondre destinataires proposés
   dans l'interface et destinataires effectivement autorisés côté serveur.
4. Supprimer seulement les surcharges rendues redondantes, avec preuve de
   non-régression. Pour chacune des méthodes conservées, justifier le besoin dans
   le code et la documentation et fournir un test qui exerce réellement ce chemin.
   Ne pas annoncer une réduction chiffrée avant cette vérification.

L'inventaire inclut `mail.mail`, `mail.message`, `mail.compose.message`,
`mail.template`, `ir.binary`, `account.move.send`, `account.move.send.wizard`,
`account.payment`, `account.payment.register`, `account.partial.reconcile`,
`payment.transaction`, `payment.link.wizard` et les contrôleurs portail ; vérifier
aussi les adaptations des documents sources, notamment `sale.order`, `account.move`
et `account.move.line`. Les protections de rapprochement, vérification bancaire,
référence, devise et absence de paiement en ligne ne sont pas des doublons à
supprimer au seul motif qu'elles ne concernent pas la confidentialité.

Le contrat réutilisable par S05 porte sur la façon de résoudre et vérifier une
autorisation, pas sur une liste universelle de bénéficiaires. Les habilitations
des programmes PDF et des dossiers sensibles S04 restent effectives. Aucun
déplacement de la logique commerciale dans le socle ni ouverture ORM générale
au portail n'est nécessaire pour #50.

**Sortie #50 avant développement S05 :** PR technique distincte, inventaire
avant/après et justification des méthodes conservées, tests proportionnés par
méthode et recette commerciale inchangée. Conserver le scénario de mise à jour
depuis S03.1 demandé par l'issue et vérifier aussi la mise à jour depuis l'état
courant #56, sans perte des fichiers et historiques S04/catalogue. Réutiliser
les scénarios CI et une base jetable ; pas de nouvelle infrastructure permanente.
La fusion garde son autorisation explicite. Ce cadrage commun ne l'accorde pas.

## Rattachements et conservation

La formation sert à retrouver les supports ; elle n'accorde aucun droit.
Un support commun référence la version exacte du programme. Son affectation à une
réalisation indique la version du fichier applicable et l'ordre de présentation.
Un support propre au groupe référence directement cette réalisation, dans la même
société et avec le même programme. L'inscription reste l'unique source des droits
du participant. Un support individuel ou une remise référence l'inscription,
jamais seulement l'entreprise cliente ou le contact commercial.

Sur la réalisation, reprendre automatiquement les références communes du programme
lors de la préparation, sans copie des fichiers. Les compléments du groupe se
déposent au même endroit. Une nouvelle version commune ne remplace pas les
références des réalisations déjà préparées : le coordinateur choisit son application
sur les fiches concernées. Aucun assistant ni nouvelle approbation requis.
Une réalisation autonome utilise les mêmes liens et ses inscriptions individuelles.

Avant diffusion, le coordinateur peut corriger le fichier. L'ouverture d'un accès,
y compris programmé, fixe les versions affectées : elles seront disponibles à la
date prévue sans dépendre d'un cron. Le gel intervient dès cette publication ;
la période S03 continue seule de déterminer quand le participant peut les lire.
Conserver la version publiée : fichier, auteur, date serveur,
empreinte, liens et date d'affectation. Remplacer crée une nouvelle version liée à
la précédente, sans écraser les octets ni les remises. Ce gel des supports est une
**décision S05**, distincte du gel contractuel déjà validé du programme.
Retirer un support bloque sa diffusion future tout en conservant la preuve interne.
Le changement de catalogue, la fin d'accès, le report et le remplacement de personne
ne suppriment aucun historique et ne transfèrent aucune remise.

Conservation et accès sont distincts : expiration S03 bloque les supports même si
leurs fichiers sont conservés. Les documents délivrés et résultats archivés auront
leurs propres droits ; leur conservation n'ouvre pas les contenus pédagogiques.
Catégories à distinguer : supports communs, affectations, remises/corrections et
échanges privés. SEC02 exige pour chacune finalité, responsable, durée, archive,
suppression et gel. Aucune durée chiffrée ni purge automatique n'est proposée par
défaut ; ces paramètres restent à valider avec S11 avant lancement. Un gel bloque
la suppression. Les exports autorisés portent un manifeste et sont journalisés.

## Droits et parcours courts

| Profil et compte | Actions proposées et périmètre | Limite |
| --- | --- | --- |
| Coordinateur interne existant | Déposer/versionner/affecter depuis programme et réalisation, retirer, consulter l'historique dans ses sociétés. | Son rôle ne donne pas automatiquement lecture de tous les échanges privés ; accès pédagogique nominatif selon mission. Aucun droit commercial nouveau. |
| Formateur externe sur portail S04 | Depuis ses séances affectées, lire les supports communs de la réalisation. | Réaffectation retire l'accès ; pas de bibliothèque intergroupes, ni de remises individuelles sans mission de tutorat/correction. Le périmètre S04 existant est conservé pour le premier incrément. |
| Tuteur ou correcteur habilité | Dans le complément S05, lire/corriger les seules remises et demandes des inscriptions affectées ; répondre et valider le critère prévu. Portail privilégié pour l'externe. | La société, le statut salarié ou la seule affectation à une séance ne donnent pas accès à toutes les conversations. L'offre autonome exige une affectation explicite sur la réalisation ou l'inscription. |
| Participant avec son compte personnel S03 | Ouvrir « Mes formations », choisir son inscription, retrouver programme, prochaines séances et supports. Déclarer une consultation seulement si l'activité le prévoit. | Le compte authentifié doit être exactement celui de l'inscription et l'accès effectif courant doit être actif. Aucune liste de pairs ni droit d'export général. |
| Client ou représentant d'entreprise | Continuer ses parcours commerciaux actuels ; futurs documents explicitement autorisés dans P05. | Aucun support privé, devoir, score ou échange individuel par défaut. Une nomination ou un mandat commercial n'est pas un accès apprenant. Un cumul de rôles utilise l'inscription personnelle pour apprendre. |
| Commercial, facturation, lecteur catalogue, qualité sans habilitation | Aucun nouveau droit pédagogique. | Lire un programme ou une commande ne donne pas accès à ses supports. |

Le parcours fréquent est une fiche existante puis un onglet Supports avec dépôt
et liste ordonnée ; côté participant, une seule page regroupe agenda et activités.
Pas d'inscription eLearning supplémentaire, de validation de diffusion distincte,
de ressaisie du programme ou de notification automatique à chaque dépôt.
Contrôler clavier, mobile, noms explicites et accessibilité pédagogique des PDF.

Chaque lecture, téléchargement ou opération portail applique côté serveur :
identité authentifiée, société exploitante, affectation exacte et, pour l'apprenant,
`training.enrollment._effective_state()` à l'heure courante. Ne pas se fier au badge,
au cron ou au groupe portail. Refus uniforme sans nom de fichier ou métadonnée d'un pair.
Les élévations éventuelles sont limitées au dossier déjà sélectionné et autorisé ;
retourner des valeurs explicitement choisies, jamais un dossier privilégié entier.
Les mutations utilisent les protections CSRF natives et des champs autorisés.

Réutiliser les protections de `training_attachment.py` et la politique issue de #50,
avec une décision d'accès unique par catégorie ; éviter une nouvelle pile de
surcharges de messagerie. Vérifier aussi lecture ORM, export, rattachement/détachement,
copie, changement de société, champ binaire, jetons limités, aperçu, URL et envoi.
Ne pas déposer les supports ou remises dans le chatter général des réalisations :
les lecteurs commerciaux S03 peuvent lire ses notes internes.

Le PDF de programme exige une adaptation ciblée de son autorisation de lecture :
`_reference_pdf()` contrôle aujourd'hui les droits ORM internes et le flux appelle
`_check_programme_pdf_access()`. Ajouter une route portail seule ne suffira pas.
Préserver empreinte et immutabilité, vérifier une inscription ou affectation autorisée
vers ce programme exact, et conserver le refus des autres URL ; ne pas ouvrir
globalement le catalogue ORM au portail pour contourner cette limite.

Une réponse privée ne doit pas être mise en cache publiquement ; revérifier les
droits avant réponse, y compris requêtes partielles et conditionnelles.
La révocation bloque les nouvelles requêtes ; elle ne peut effacer un PDF déjà
téléchargé ni rappeler des octets déjà reçus. Filigrane, interdiction de téléchargement,
antivirus externe, DRM ou lien à durée spéciale seraient des options nouvelles,
pas des exigences déjà validées.

## Articulation avec progression et tutorat

Le complément S05 conserve, par activité applicable et inscription, le critère
explicite : consultation déclarée, remise, validation du formateur ou seuil
d'évaluation. Ouvrir le PDF ne valide ni compétence ni présence. Le facultatif
ne bloque pas la complétion ; les dépendances sont contrôlées sans cycle.
Les résultats d'examen seront fournis par S06, sans calcul parallèle ici.

Les remises et corrections restent privées et versionnées, avec statut, auteur et
date. L'aide est liée à l'inscription et au tuteur affecté ; aucune pièce ni texte
privé dans un courriel collectif. Réutiliser la file de courriels native pour les
notifications autorisées, sans joindre le contenu privé. Contrôler destinataire et
habilitation lors de l'envoi et de la reprise, conformément à #50.
Échéances et seuil d'inactivité viennent de l'offre ; journaliser les relances et
éviter les doublons. Suspension justifiée et activité facultative ne produisent
pas de relance inadéquate. La réservation autonome de créneaux reste P13.

## Décisions retenues

| Décision réelle | Choix le plus simple et recommandation | Conséquence |
| --- | --- | --- |
| Étendue du premier développement | Réaliser et faire fusionner #50 d'abord, puis espace/programme/agenda/supports, puis le complément progression/remises/tutorat dans S05. | Un cadrage commun et des livraisons vérifiables séparées ; #15 reste ouverte jusqu'à livraison complète. Livrer tout S05 ensemble après #50 augmente le premier lot fonctionnel sans supprimer ces exigences. |
| Standard de diffusion | Portal et `ir.attachment` déjà présents, avec rattachement et autorisation ciblés ; recommandés. | Pas de dépendance supplémentaire. Retenir eLearning impose Website et ses dépendances, un lien aux inscriptions S03 et la sécurisation de ses routes et actions ; sa configuration seule ne suffit pas. |
| Destinataires des supports communs | Tous les inscrits actuellement autorisés de la réalisation ; aucun accès client par défaut. Recommandé. | Aucun sélecteur de sous-groupe à maintenir. Un besoin de diffusion à certains inscrits d'une même réalisation nécessiterait une sélection explicite, sans inventer un groupe ou élargir P05. Les remises restent toujours individuelles. |
| Version applicable et mise à jour | Références reprises à la préparation ; versions diffusées conservées ; remplacement explicite depuis la fiche, sans validation supplémentaire. Recommandé. | Une correction commune ne se propage pas silencieusement aux anciennes réalisations. Le choix opposé d'une bibliothèque vivante simplifie la propagation mais perd la stabilité du support applicable. |

Les durées de conservation et paramètres d'accompagnement sont des paramètres de
lancement encore à fixer, pas un prétexte à ajouter un écran ou à deviner des valeurs.

## Recette prévue

**Préalable #50 :** avec de vrais comptes portail et internes restreints, vérifier
devis, facture, reçu, avis de virement, messages et pièces jointes ; autoriser le
contact prévu et refuser celui d'un pair, d'une autre entreprise ou société.
Inclure URL et jetons directs, pièces de messages, lecture/export, abonnés,
adresses libres, destinataires forcés par API, révocation avant transport et reprise.
Pour les reçus, tester intersections, paiement non affecté et factures mixtes.
Vérifier aussi les documents hors formation, qui doivent conserver leur comportement
natif, et la séparation des rôles coordination/commerce/facturation. Réutiliser
notamment `test_training_portal_http.py` ; les tests existants sont un point de
départ, pas une preuve automatique de couverture de chaque méthode conservée.
Rejouer acomptes, règlements partiels, avis sans effet comptable, rapprochements,
contrôles de devise/référence et refus de paiement en ligne. Installation vierge,
reprises S03.1 et #56 et conservation des historiques complètent la sortie #50.

**Fonctions S05 après ce préalable :**

1. Coordinateur : déposer un PDF commun sur le programme, préparer deux réalisations,
   ajouter un support de groupe, ouvrir les listes sans ressaisie. Participant : programme
   exact, agenda S04 et supports sur la même page. Autonome : aucun horaire fictif.
2. Avec vrais comptes restreints : autoriser A et refuser B, autre groupe, autre
   entreprise, autre société, client mandaté, commercial, facturation et public.
   Tester liste, détail, identifiant deviné, export et toutes les variantes de fichiers,
   images, champs, jetons anciens/limités et PDF programme. Aucun nom privé divulgué.
3. Avant ouverture, à expiration sans cron, en suspension/révocation, retrait commercial,
   désactivation de compte et réaffectation formateur : nouvelle requête refusée.
   Tester requêtes partielles/conditionnelles, cache, cumul de rôles et changement d'employeur.
4. V1 diffusée puis V2 : mêmes octets V1 et références historiques, choix explicite
   d'affectation V2 ; retrait sans purge, report/remplacement sans transfert de remise.
   Refuser écrasement, changement public/jeton, détachement et copie détournée via API.
   Tester répétition, concurrence et échec de dépôt sans doublon ni pièce orpheline exposée.
5. Complément S05 : ouvrir un PDF ne prouve pas l'acquisition ; déclaration selon critère,
   facultatif non bloquant, cycle refusé, remise corrigée par le tuteur seul, échange
   d'un pair inaccessible. Suspension/facultatif sans relance inadéquate ; reprises sans doublon.
6. Vérifier parcours mobile/clavier, PDF représentatifs, installation vierge et mise à jour
   depuis #56 avec historiques conservés ; non-régression S02/S03/S04 et PDF du programme.
   Vérifier l'ensemble des modules réellement installés, y compris Website/eLearning s'ils sont présents.

Ces scénarios sont des critères futurs. La conformité du portail, les refus HTTP,
les performances et les parcours complets S05 restent à démontrer lors du développement.
Les résultats d'exécution appartiendront à la PR, sans les recopier dans cette page.

## Premier incrément : espace et supports

Le socle utilise Portal et le champ binaire natif de `training.material`, stocké
une seule fois dans `ir.attachment`. `training.material.assignment` conserve les
références ordonnées de chaque réalisation. Les droits ORM restent réservés aux
coordinateurs de la société ; le portail ne reçoit que des valeurs sélectionnées.
Le service privé `training.document.policy` est défini dans le socle et étendu par
Ventes : les contrôles binaires et de transport de #50 restent communs, sans
ouverture des habilitations commerciales vers la pédagogie. Les PDF privés ne
sont pas joints à des courriels ; aucune notification de dépôt n'est créée.

Depuis le programme, **Supports PDF privés → Ajouter un PDF privé**. La création
d'une réalisation reprend les dernières versions communes non retirées. Depuis la
réalisation, le même onglet permet d'ajouter un PDF de groupe ou une référence
explicite. **Ajouter les PDF du programme** complète les références sans remplacer
les anciennes et reste sans effet lors d'une répétition. Une version retirée ne
réactive pas sa précédente. Une correction utilise **Nouvelle version PDF** ;
retirer l'ancienne référence reste un choix explicite. Les références, auteurs,
dates et empreintes sont conservés. Le verrou natif avec barrière d'écriture
sérialise modification du fichier et première diffusion. L'aperçu PDF natif revérifie
le droit courant même avec un jeton de propriété, et interdit la mise en cache.
Les exports en masse des supports et références, y compris depuis une fiche liée
ou les pièces jointes, sont refusés en attendant le manifeste et la journalisation
S11. Les téléchargements autorisés restent disponibles, sans mise en cache.

L'ouverture d'accès d'un inscrit, active ou programmée, gèle les versions affectées.
La disponibilité au formateur affecté d'une réalisation confirmée le gèle également : le formateur
ne reçoit donc jamais une version encore modifiable. **Mes formations** rassemble
programme applicable conservé, agenda S04 et supports, sans compte eLearning.
L'offre autonome n'affiche aucune séance fictive. Les séances affectées S04 donnent
au formateur les supports de la réalisation ; une réaffectation retire ce droit.
Chaque nouvelle requête réévalue identité, société et accès effectif S03, y compris
sur les URL natives avec jeton, téléchargement partiel ou requête conditionnelle.
Les réponses pédagogiques ont `Cache-Control: private, no-store`.

Les versions de module deviennent `20.0.1.5.0` (socle) et `20.0.1.10.5` (Ventes).
Mettre à jour les deux modules. Le pont temporaire de défaut Website reprend le
mécanisme du lot PDF et restaure le schéma natif après chargement des vues.
Le scénario `tests/ci/run_s05.sh` reprend #57 avec Website/eLearning, compare les
historiques documentaires/comptables et le PDF, puis exerce deux transactions
concurrentes. Les tests `test_material.py` complètent la recette ci-dessus.
Les résultats réellement exécutés restent dans la PR.

Ce premier incrément ne clôt pas #15 : progression, activités, remises/corrections,
aide privée, tuteurs et relances restent le complément S05 prévu au lancement.
Ouvrir un PDF ne produit aucune progression, acquisition ou présence.
