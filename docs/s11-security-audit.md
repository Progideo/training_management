# S11 — Sécurité transversale, conservation et accès

Référence : [cadrage #21](https://github.com/Progideo/training_management/issues/21#issuecomment-6387150408),
SEC01–SEC02 et matrice des rôles §10 de la spécification. Le socle reste Odoo
Community `20.0-20261015` ; aucune dépendance supplémentaire.

Les groupes, ACL, règles d’enregistrement, utilisateurs, pièces jointes,
contrôleurs, exports et vues restent ceux d’Odoo et des modules officiels. Le code
exact du résolveur `ir.binary`, du diagnostic `ir.access` et de l’export ORM a été
pris comme référence. `ir.exports` conserve les modèles de colonnes d’export,
pas un journal des extractions : le seul nouveau modèle S11 conserve le manifeste
exigé par SEC02. Les règles spécifiques complètent les contrôles natifs aux
frontières où un jeton ou un export d’identifiant peut les contourner.

## Matrice des frontières et preuves

| Surface | Autorisation et trace | Tests de référence |
| --- | --- | --- |
| Catalogue, réalisations, inscriptions | Groupes, règles par société exploitante ; le client reste un contact distinct. Utilisateur archivé exclu des règles par société. | `test_catalogue`, `test_enrollment`, `test_security` |
| Aménagements et historique | Référent/suppléant nommé ; fichiers et aperçus recontrôlent cette mission courante. Historique et manifeste d’export S04 conservés. | `test_preparation`, `test_security` |
| Supports, tutorat et échanges | Inscription effective ou mission explicite ; pas de droit hérité d’un auteur/follower/jeton. | `test_material`, `test_learning` |
| Examens et réponses Survey | Règles propres à Surveys et aux tentatives ; refus des voies natives hors périmètre. Les fichiers de réponses aux questionnaires restent inaccessibles, même avec un jeton d’aperçu. | Surveys : `test_exam`, `test_feedback`, `test_security`, `test_native_regression` |
| Présences et justificatifs | Affectation à la séance et état courant ; dépôt, validation et correction distincts ; historique immuable. | `test_attendance` |
| Attestations, preuves, ZIP | Qualité affectée ; destinataires client choisis puis figés, habilitation actuelle requise ; aucun transfert par changement d’employeur. Manifeste et empreinte conservés. | `test_closure` et intégration Surveys |
| Évaluations, retours, qualité, intervenants | Missions explicites, périmètre société et catégories privées ; réponses anonymes restituées dès trois réponses, sans contrôle supplémentaire. | `test_evaluation`, `test_feedback`, `test_quality`, `test_provider` |
| Tableau de suivi | Une ligne par inscription autorisée ; retrait de mission appliqué aux lectures, recherches, regroupements et exports. Manifeste S10 conservé. | `test_dashboard` et intégrations |
| Commercial et facturation | Standard Sales/Accounting et politique documentaire ciblée ; contacts explicitement habilités, aucun accès pédagogique implicite. | Suite `training_management_sale` |
| Exports natifs | Vérification des règles avant toute ligne, même pour le seul identifiant ou une relation imbriquée. Manifeste serveur par société : acteur, date, modèle, identifiants, colonnes, population, empreinte. | `test_security`, `test_preparation`, `test_dashboard` |

Ces références composent la suite cumulative ; ce tableau ne signifie pas que
chaque combinaison de droits est certifiée. Les tests exécutés et leurs limites
restent dans la PR. Les changements de missions continuent d’être tracés dans
`training.operation` ou les historiques privés du workflow concerné.

## Compléments transversaux

Les aménagements rejoignent la politique documentaire commune pour le
téléchargement, l’aperçu PDF et les en-têtes `private, no-store`. L’ancien jeton
ne remplace jamais la mission courante ; les fichiers ordinaires Odoo conservent
leur fonctionnement natif. Les courriels ne distribuent pas ces pièces, ni les
fichiers privés d’examen ou de réponse. Les notifications métier continuent de
recontrôler leurs destinataires au transport.

Les refus des modèles `training.*` donnent une erreur générique, y compris en
mode développeur : aucun nom de participant, sujet ou nom de fichier n’est
résolu pour le diagnostic. Les journaux serveur ajoutent les identifiants
d’acteur, société, modèle et source lors de la préparation autorisée d’un fichier
protégé, et signalent le contexte privilégié. Ces nouvelles traces ne recopient ni contenu, ni
adresse, ni jeton. Une préparation de flux ne prouve pas sa réception complète.
Leur accès et conservation relèvent de l’exploitation ; aucun droit de support
exceptionnel nouveau n’est accordé.

« Mes manifestes d’export » présente seulement les nouveaux manifestes de
l’acteur, dans ses sociétés sélectionnées. Ils ne contiennent pas les valeurs
exportées et n’ouvrent aucun accès aux sources. Ils sont immuables et exclus de
l’export en masse. Les manifestes S04 et S10 existants restent leurs sources de
référence, sans double journal. Le hook ORM hérité de `base._export_rows` ne
modifie le comportement que des modèles `training.*` et des examens Surveys
rattachés à Training Management, après leurs propres protections. Les enquêtes
ordinaires restent natives ; aucun patch du cœur.

## Conservation et instruction humaine

Réutiliser les [politiques, versions et gels S08](s08-closure-documents.md#exports-et-conservation),
les gels qualité S09.3 et intervenants S09.4, ainsi que les historiques et
tentatives conservés S05–S07. Les paramètres réels par catégorie (finalité,
responsable, durée, archive et suppression) doivent être approuvés par le
responsable métier avant collecte réelle. Une valeur fictive de test n’est pas
une durée légale ou une configuration de lancement.

Une demande de suppression est instruite dans un dossier qualité privé :
identifier le périmètre et son responsable, vérifier les politiques et gels,
consigner la décision motivée et les suites autorisées. S11 n’exécute aucune
suppression physique ; une éventuelle intervention nécessite une instruction
distincte et une vérification des obligations et gels. Aucune purge automatique
des tentatives, preuves, journaux ou exports, même après expiration d’une durée.

## Recette courte

1. Avec deux coordonnateurs distincts, créer une inscription fictive et son
   aménagement. Joindre un PDF fictif. Le référent peut le télécharger et
   l’apercevoir ; l’autre profil reçoit un refus, même avec l’ancien lien.
2. Ajouter ce profil comme suppléant, ouvrir le PDF, retirer la mission puis
   réutiliser les liens d’aperçu et de téléchargement : refus sans nom privé.
   Vérifier les en-têtes sans cache, y compris avec `unique` et un jeton.
3. Répéter avec un PDF d’examen et un fichier de réponse Survey : seul le
   coordonnateur actif peut ouvrir le premier ; aucun profil ne reçoit le second
   par l’aperçu natif. Vérifier qu’une pièce Odoo ordinaire reste accessible selon
   les règles natives. Aucun envoi SMTP réel pendant la recette.
4. Exporter une inscription autorisée, y compris le seul identifiant : retrouver
   son manifeste et son empreinte ; l’autre acteur ne le lit pas. Un profil hors
   périmètre ne peut pas exporter l’identifiant deviné. Essayer aussi après
   archivage du compte et après retrait d’une mission S10.
5. Vérifier les historiques privés, un dossier sous gel, ses fichiers et son
   export conservé après mise à jour puis seconde mise à jour. Aucun contenu
   ancien ni export ne doit être régénéré ; aucune notification rétroactive.

L’installation est couverte par les huit configurations existantes. La mise à
jour depuis `44a85c5` ajoute un parcours de migration avec empreintes des colonnes
historiques, fichiers, politiques et gels ; il ne relance pas la suite métier.
