# S09.3 — Réclamations et amélioration continue

QUA01–QUA02 de [la spécification v2](references/Training_Management_Specification_Fonctionnelle_v2.md),
selon le [cadrage S09 validé](s09-evaluations-quality.md). Socle `20.0.1.11.0`.
S09.4 et le tableau consolidé S10 restent distincts. L’anonymat S09.2 conserve
son seuil de trois réponses, sans contrôle supplémentaire.

## Parcours et confidentialité

**Formations → Réclamations** : sujet et texte d’origine, auteur, canal,
réalisation/inscription éventuelles, responsable, échéance et conservation.
Reçue → en traitement → résolue avec réponse → clôturée. La résolution exige une
réponse et un traitement, une action liée ou une justification. Une réouverture
motivée conserve les anciennes réponses et dates dans l’historique privé.

**Formations → Actions d’amélioration** : origine (réclamation, campagne de
retours, revue ou autre), référence, responsable, échéance, décision, critère et
plan de vérification. À décider → planifiée → réalisée → efficacité à vérifier →
efficace / inefficace. La réalisation exige le résultat ou support corrigé ; elle
ne conclut jamais automatiquement à l’efficacité. La qualité documente la
vérification ; un échec impose une suite. La replanification motivée conserve la
vérification antérieure dans l’historique. Les champs du nouveau cycle sont
vidés : réalisation, support corrigé, dates, vérification, vérificateur et suite.

Les habilitations sont propres à chaque dossier : référent qualité et personnes
explicitement habilitées de la qualité ou de la coordination. Aucun accès global
au contenu sensible par le seul rôle. Les autres rôles n’obtiennent aucun accès
supplémentaire. Le retrait d’une habilitation ou la réaffectation du référent
retire les accès qui en dépendent aux historiques, fichiers et actions issues de
la réclamation. Une habilitation indépendante doit être retirée explicitement. Les sociétés exploitantes restent isolées.
Un refus d’accès ne révèle ni sujet ni nom de fichier, y compris en mode développeur.

Les fichiers privés sont non modifiables, avec source, date et empreinte.
Ils peuvent être ajoutés dès la création du dossier. Les actions liées sont
consultables depuis la réclamation selon les habilitations de chaque action.
Une correction ajoute une version liée ; aucune suppression métier. Les
échéances apparaissent dans les listes avec le filtre **En retard**. Les messages,
pièces jointes et activités partagées ne transportent pas le contenu privé.

Le participant utilise **Mon compte → Mes réclamations confidentielles**. Pour
activer le dépôt, la coordination configure dans la réalisation le référent,
une politique de conservation approuvée et son délai cible de réponse. Aucun
délai légal n’est présumé. L’expiration des supports et la clôture de l’inscription
ne suppriment pas ce recours ; une suspension ou un retrait explicite d’accès
le bloque. Le portail exige une inscription confirmée ou clôturée avec autorisation
commerciale courante. Il reçoit un texte et affiche uniquement sa propre
réclamation et la réponse après résolution. Il n’expose ni notes internes,
ni personnes habilitées, ni fichiers internes. Le dépôt de fichiers reste réservé
aux personnes habilitées dans le dossier interne. Les doubles envois du même
formulaire conservent une seule réclamation et son texte d’origine.

Les politiques approuvées et le gel de conservation réutilisent S08 : aucune
période réglementaire ni purge automatique ajoutée. Le gel bloque les mutations
jusqu’à sa levée par le référent qualité affecté.

## Raccord S08

L’action **Synthèse approuvée pour S08** demande une synthèse minimale explicite,
un traitement ou une décision d’efficacité terminé et un dossier S08 ouvert de
la même réalisation, affecté au même utilisateur qualité. Elle crée une preuve
PDF sensible, non partagée au client, avec provenance et version. La validation
qualité S08 reste distincte. Aucun texte intégral de réclamation ni fichier
interne n’est copié automatiquement. Les anciens PDF restent inchangés.

## Recette courte

Utiliser uniquement des données fictives, un coordinateur, deux référents
qualité et deux participants de réalisations distinctes.

1. Configurer la réception d’une réalisation. Avec son participant, déposer une
   réclamation puis renvoyer le même formulaire : un seul dossier. Vérifier le
   texte d’origine et l’absence d’accès à la réclamation de l’autre participant.
2. Affecter le dossier à un référent et un coordinateur. Vérifier que le second
   référent ne le trouve ni dans les listes, ni par URL, export ou téléchargement.
   Retirer le coordinateur puis réaffecter le référent : leurs anciens accès
   doivent disparaître, y compris aux fichiers et historiques.
3. Commencer le traitement. Essayer de résoudre sans réponse et de clôturer avant
   résolution : refus. Renseigner traitement et réponse, résoudre puis clôturer.
   Le participant voit la réponse, jamais le traitement interne. Rouvrir avec
   motif : historique conservé, réponse précédente masquée au portail.
4. Créer l’action liée. Planifier avec critère et plan, enregistrer réalisation et
   support corrigé : efficacité encore à vérifier. Conclure à un échec sans suite :
   refus ; documenter la suite, replanifier, puis vérifier à nouveau.
5. Ajouter un fichier privé, essayer de le remplacer ou de le télécharger avec
   un utilisateur tiers : refus. Ajouter une version corrigée ; conserver les
   deux. Poser le gel et vérifier le blocage des modifications.
6. Exporter une synthèse minimale vers S08. Contrôler le PDF, la confidentialité
   sensible, l’absence de partage client et la validation séparée. Répéter : pas
   de doublon ; une nouvelle synthèse conserve l’ancien PDF. Un dossier S08 fermé
   ou d’une autre réalisation doit être refusé.
7. Sur écran mobile puis au clavier seul, parcourir le formulaire portail, les
   erreurs et le retour à la liste ; vérifier les libellés français, le focus,
   l’absence de débordement avec un sujet et un texte longs sans espaces, la date
   de réception localisée et l’accès à tous les champs et boutons. Contrôler aussi
   les assistants qualité, dont le bouton **Annuler**.
