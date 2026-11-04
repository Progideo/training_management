# Validation formative et limites du lecteur commun

Suite du cadrage du 3 novembre et du raccordement autonome. Les adaptateurs TM et
cours natifs consomment désormais un même validateur de rapports formatifs : JSON
borné à 128 Kio, nombres finis, score non négatif borné par le maximum, booléen de
complétion explicite et résultat entier sur un pour H5P TrueFalse 1.8. La validation
ne transforme pas une déclaration du navigateur en évaluation certifiée.

La bibliothèque reste autonome et ne dépend d’aucune des deux applications métier.
Les fichiers, versions, lecteurs, origines isolées et autorisations courtes restent
uniques. Les tentatives et projections pédagogiques appartiennent aux adaptateurs.
Le libellé des versions inclut la ressource pour distinguer plusieurs numéros égaux.

Les vidéos privées sont hors périmètre au lancement. Les imports refusent les
extensions vidéo usuelles et le lecteur applique `media-src 'none'`, sans ajouter
un service d’hébergement ou de lecture vidéo. Les octets historiques ne sont ni
réécrits ni supprimés automatiquement. Les limites H5P TrueFalse 1.8 et SCORM 1.2
mono-SCO demeurent inchangées.

Validation : installation minimale réelle de la bibliothèque seule, reprise et
contrôles HTTP du lecteur, validation des nombres excessifs/non finis et des tailles.
Les résultats et la composition exacte figurent dans la pull request.
