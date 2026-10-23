# S08 — Attestations, preuves et clôture

Référence : [#18](https://github.com/Progideo/training_management/issues/18), DOC01–DOC02,
SEC01–SEC02 et chapitres 13–14 de la spécification.

## Standard et choix

Sur Community `20.0-20261015` épinglé : `ir.actions.report` fournit QWeb et le
moteur PDF, `ir.binary` les téléchargements, l’ORM les droits et verrous.
Le cache de rapports natif ne conserve pas seul les critères pédagogiques,
les versions des preuves et les décisions de clôture. Le modèle Certification
Survey concerne une tentative ; il ne démontre pas la réussite d’une formation.
Aucune dépendance Enterprise ou application séparée n’est ajoutée.

Les extensions restent dans le socle : un dossier par inscription, lié à sa
réalisation, son programme et son client d’origine ; des preuves versionnées ;
des PDF et exports conservés. Pour une réalisation réunissant plusieurs clients,
ce périmètre évite de réunir leurs dossiers dans un téléchargement commun.
Les pièces communes sont référencées dans la provenance puis déposées dans le
périmètre contrôlé de chaque dossier. Leur pertinence reste contrôlée humainement.

## Parcours et règles

1. Attribuer explicitement le rôle qualité. Ce rôle seul n’accorde l’accès qu’aux
   dossiers affectés ; il ne donne pas les pouvoirs du coordinateur.
2. La qualité approuve une politique de conservation : finalité, responsable,
   durée et traitement d’archive/suppression. Aucune durée juridique n’est inventée.
3. Le coordinateur crée le dossier depuis l’inscription, choisit son responsable
   qualité et la politique approuvée. L’identité du client est conservée.
4. Déposer les PDF et leur provenance : auteur original, date de production,
   source et identifiant de document/événement d’origine. L’ORM conserve aussi
   le déposant et sa date serveur. Chaque ajout dans une catégorie crée une version
   liée à la précédente. La qualité valide les pièces ou une non-applicabilité/
   dérogation motivée. Une version validée ne se réécrit ni ne se supprime.
5. La qualité délivre les attestations directement dans le dossier de l’inscription confirmée ou terminée :
   participation = somme des seules durées S07 retenues et validées ; réalisation =
   activités S05 obligatoires terminées et justificatif de réalisation contrôlé ;
   réussite = PDF d’évaluation dédiée des acquis, score et seuil validés.
   Une dérogation ne remplace pas ces critères de délivrance. Un examen blanc réussi
   n’alimente jamais automatiquement cette évaluation dédiée.
6. Contrôler les manquants, puis clôturer. Les catégories reprennent le dossier
   minimal du chapitre 14, avec une pièce de contrôle de réalisation distincte.
   Une nouvelle version en attente rend sa catégorie manquante. La clôture exige
   une dernière version validée dans chaque catégorie ; elle conserve ses dérogations.

Le PDF QWeb `S08-QWEB-1` conserve bénéficiaire, programme/version, référence,
dates, auteur d’émission et critères utilisés dans un instantané. Sa référence
varie avec les critères ; répéter une émission identique rend le même PDF.
Une correction S07 ne réécrit jamais un PDF antérieur. Une évolution du modèle
exige un nouvel identifiant de version. Les dates imprimées sont en UTC.

Les preuves sensibles sont réservées au responsable qualité affecté. Les fichiers
utilisent le champ binaire natif privé sans pièce jointe autonome ni jeton de partage.
La politique documentaire réévalue l’utilisateur réel, même après résolution
native avec élévation ou jeton. Seul le champ fichier est téléchargeable ; aucun
instantané privé n’est exposé par la route binaire. Aucun envoi par messagerie.
Les élévations sont limitées aux métadonnées d’autorisation, à l’instantané de
présence validée et au verrou S03, après contrôle du dossier.

## Exports et conservation

L’export qualité contient les pièces validées, leurs versions et un index JSON
avec provenance, auteurs, dates, validation, confidentialité, empreintes et
manquants. Chaque ZIP est conservé avec auteur, date, périmètre et empreinte.
Un dossier incomplet peut être exporté : son index le signale.

L’export client exige des contacts explicitement choisis dans le client du dossier.
Il inclut seulement les PDF cochés partageables dans les catégories autorisées,
et les attestations dont le partage a été explicitement choisi avant émission.
Les évaluations individuelles, positionnement, retours, incidents et contrôles
privés sont exclus, y compris leurs métadonnées et leurs motifs. Les contacts
sont figés dans l’export ; le téléchargement exige aussi leur habilitation actuelle.
La liste « Mes documents de formation » présente seulement les fichiers autorisés
au participant ou au contact client. Aucun droit ne vient d’un changement d’employeur.

Un dossier clôturé et ses versions sont conservés. Le gel est explicite ; aucune
purge automatique n’existe, même à échéance de conservation. Une demande de
suppression exige une instruction humaine distincte. Les exports antérieurs ne
sont pas régénérés. Les verrous S03 et leur révision protègent émission, validation,
export et clôture des requêtes concurrentes périmées.

Un dossier complet ne vaut ni certification Qualiopi, ni validation par un financeur.
Les attestations ne confèrent aucune certification officielle. P20 reste hors périmètre.

## Recette courte

1. Avec un coordinateur, ouvrir un dossier et déposer une preuve ; vérifier la
   provenance et la version. Avec le responsable affecté, valider puis tenter de modifier.
2. Sans présence validée, refuser la participation. Après contrôle d’une présence
   partielle, vérifier sa durée réelle sur le PDF ; répéter puis corriger la présence.
3. Refuser réalisation sans activités/justificatif et réussite sans évaluation
   dédiée au seuil, même après réussite d’un examen blanc.
4. Exporter un dossier incomplet, lire l’index ; approuver des motifs de
   non-applicabilité/dérogation puis clôturer. Vérifier le gel des historiques.
5. Comparer ZIP qualité et client ; vérifier deux clients, deux participants,
   une société étrangère, un formateur non habilité et un autre responsable qualité.
   Retirer un contact et réessayer son lien avec jeton ; tester aussi un champ privé.
6. Exécuter `tests/ci/run_s08.sh` : installation vierge, mise à jour S07 avec
   Website, historiques S02/S05/S06/S07/S08 et concurrence réelle. Les résultats
   d’exécution restent dans la PR.
