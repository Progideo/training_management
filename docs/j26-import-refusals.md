# J26 — Motifs de refus des paquets interactifs

Référence : #146. La bibliothèque commune traduit les motifs connus du parseur au niveau ORM. Le parseur reste indépendant d’Odoo ; les limites ZIP, chemins, formats et contrôles de sécurité ne changent pas. Un motif inconnu reçoit un message générique traduit, sans détail interne brut.

Les refus ne créent ni version ni fichier de ressource. Aucune migration de contenu ni modification des versions publiées.

## Recette courte

1. En français, importer des fichiers fictifs avec manifeste invalide, chemin interdit, SCORM 2004, bibliothèque H5P non prise en charge et taille supérieure à 20 Mio.
2. Vérifier un refus compréhensible en français et les saisies conservées.
3. Annuler et vérifier les mêmes versions publiées, empreintes, accès et progressions.
