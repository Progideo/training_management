# Bibliothèque interactive commune

Suite de [J1 #123](https://github.com/Progideo/training_management/issues/123),
après le [catalogue commun](j1-shared-catalog.md). Cadrage consolidé du 3 novembre
2026, D09/D21/D32/D36/D38. Cette tranche reste une préparation de l'indépendance ;
les examens communs et l'application autonome restent à réaliser.

## Frontière livrée

`training_interactive` dépend seulement de `training_catalog`. Il possède
l'identité des ressources, les versions, les fichiers privés, le contrôle
d'import et les assistants d'import/retrait. Le contrôle ZIP et les limites
H5P TrueFalse 1.8 / SCORM 1.2 mono-SCO sont repris du correctif eLearning
`d7d3b976d07831bca2de3c75d6c159308adf7f0d`, sous la même licence LGPL-3.0-only.
Aucun paquet n'est extrait sur disque ou copié dans les fichiers statiques.

Les noms techniques existants `training.elearning.resource`, `.version`, `.file`,
`.import` et `.withdraw` sont conservés afin de préserver les références. Leur
implémentation appartient désormais à la bibliothèque commune. Le manifeste
n'utilise ni TM, ni Survey, ni slide ; aucun apprenant ou compteur n'est ajouté.

L'addon historique `training_management_elearning`, dans l'autre dépôt,
réutilise ces objets. Ses lecteurs, autorisations courtes, affectations,
tentatives, progression TM et questions enrichies y restent pour cette tranche.
Un import de compatibilité redirige son ancien parseur vers l'unique parseur
commun. Le raccordement final TM et les lecteurs communs restent à extraire
avant la nouvelle application autonome ; le graphe cible à dix addons est inchangé.

## Droits et conservation

L'auteur interne habilité importe et publie directement dans ses sociétés.
Le gestionnaire hérite de ce rôle et peut retirer une version avec motif ;
date, auteur et décision initiale sont conservés. L'ancien groupe auteur est
raccordé au rôle commun ; la coordination TM reçoit le rôle de gestionnaire
uniquement lorsque l'adaptateur historique est installé.

Aucune permission sur les inscriptions ou résultats TM n'est accordée à l'auteur
commun. Les octets des paquets restent interdits aux accès ORM et URL natives,
y compris avec un jeton de champ ou une pièce jointe déclarée publique. Les
lecteurs existants doivent passer par leurs autorisations et leur origine isolée.
Le socle seul ne propose aucune lecture de paquet. Un retrait ne remplace ni la
version ni les acquis ; la notification et le traitement métier des apprenants
concernés restent à compléter dans les futurs adaptateurs.

Les imports sont contrôlés en mémoire et atomiques. Identité, société, format,
versions et octets historiques restent immuables ; l'archivage conserve les
références. Import/publication et archivage sérialisent l'accès à la ressource.
Aucune migration historique ou désinstallation de l'ancienne composition n'est
qualifiée. La mise à jour porte sur des bases neuves de cette génération.

## Point d'extension des attestations TM

La clôture appelle désormais `training.learning.service._required_for_certificate`.
Le comportement TM par défaut conserve les activités obligatoires. L'adaptateur
interactif peut exclure les ressources formatives non désignées pour l'achèvement,
ou inclure celles dont l'affectation le prévoit explicitement. Ce point d'extension
était appelé par l'extension historique mais absent du socle de référence.

La preuve dédiée, la qualité habilitée, les autres activités requises, la génération
PDF et les règles P20 restent appliquées. Une complétion interactive ne signe
aucune présence et ne délivre pas de document automatiquement.

## Recette courte

1. Installer `training_interactive` seul sur une base neuve ; importer des paquets
   fictifs des deux formats, puis publier avec un auteur sans rôle TM.
2. Refuser société étrangère, portail, publication par un utilisateur non habilité,
   modification des octets et téléchargements natifs, même avec jeton.
3. Retirer une version avec un gestionnaire ; conserver les deux versions et la
   décision initiale. Mettre à jour et rapprocher UUID, états, acteurs et SHA-256.
4. Installer la composition raccordée avec le commit eLearning associé : reprendre
   une tentative, conserver son acquis après un résultat inférieur, vérifier les
   refus directs et l'émission manuelle d'attestation avec obligations explicites.

Commande du socle : `python3 tests/ci/run_j1_interactive.py`. La composition de
l'autre dépôt se vérifie avec son banc et son `compatibility.json` épinglé.
Les résultats réels restent dans les PR. Les essais de navigateur des lecteurs
isolés et la qualification des nouvelles applications restent distincts.
