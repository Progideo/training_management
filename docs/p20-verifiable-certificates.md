# P20 — Attestations vérifiables

Référence : [#105](https://github.com/Progideo/training_management/issues/105),
DOC01/SEC02, chapitre 23. Extension ciblée de [S08](s08-closure-documents.md).

## Parcours et règles

Le coordinateur coche « Émettre des attestations vérifiables » dans le dossier.
Le responsable qualité affecté délivre ensuite les attestations selon les critères
S08 habituels. Participation, réalisation et réussite sont couvertes ; aucune
réussite d’examen blanc ne déclenche d’attestation automatiquement.

Le nouveau PDF `P20-QWEB-1` contient un lien et un QR code natif Odoo. Les anciens
PDF `S08-QWEB-1`, preuves et exports sont conservés, sans publication rétroactive.
Activer l’option puis délivrer produit un nouveau document ; répéter une émission
avec les mêmes critères conserve le même PDF, lien et statut, même après révocation.
Les émetteurs utilisent l’URL de base native de leur environnement Odoo.

La projection publique validée comprend uniquement : émetteur, **nom complet du
bénéficiaire**, référence, type, formation/version, date d’émission UTC, statut et
empreinte SHA-256 du PDF. Ces mentions sont figées à l’émission. Aucun PDF, score,
seuil, résultat d’examen, dossier, contact client, motif ou auteur de révocation
n’est accessible par cette page. Le lien utilise un jeton aléatoire de 256 bits,
distinct des identifiants internes. Aucun droit de lecture public sur le registre
n’est ajouté ; le contrôleur ne retourne qu’une projection explicite.

Le responsable qualité affecté ouvre la vérification depuis le dossier, puis
choisit « Révoquer » ou « Remplacer », avec un motif. Le remplacement exige une
attestation vérifiable encore valide du même dossier et du même type. Il faut
l’émettre au préalable après correction des critères. Si le dossier est clos, utiliser la [rectification motivée](review-access-continuity.md), puis le clôturer à nouveau. La décision conserve auteur,
date et lien interne vers le remplacement. Révocation et remplacement sont définitifs,
restent possibles après clôture, ne réécrivent aucun PDF et ne rétablissent jamais
silencieusement un statut. Une correction S07 seule ne révoque pas les anciens PDF.
Aucune échéance arbitraire n’est ajoutée.

Le vérificateur retrouve « valide », « révoquée », « remplacée » ou « inconnue ».
Une inconnue répond HTTP 404. Les réponses n’autorisent aucun cache ni indexation.
La page ne renvoie pas vers le remplacement : elle ne publie pas un autre lien
à partir du document invalidé. Pour contrôler l’ensemble du fichier présenté,
comparer son SHA-256 ; un QR copié sur un autre fichier n’en prouve pas l’intégrité.
Cette vérification ne constitue aucune certification officielle ou Qualiopi.

## Intégration et sécurité

Community `20.0-20261015`, image épinglée par la CI : `ir.actions.report.barcode`
génère le QR et QWeb l’intègre au PDF sans appel externe. Les rapports Surveys
portent une tentative et ne remplacent pas les attestations de formation S08.
Aucune dépendance ni application supplémentaire. Les contrôles d’accès réévaluent
le rôle qualité affecté et la société autorisée, même sur un recordset élevé.
Les écritures libres, copies et suppressions du registre sont interdites. Le verrou
S03/S08 commun sérialise émissions et changements de statut ; une transaction
périmée doit être rejouée. Les dates et motifs de la première décision sont conservés.

## Recette courte

1. Émettre sans l’option, conserver le PDF ; activer l’option et réémettre.
   Vérifier conservation de l’ancien, nouveau modèle, lien, QR et absence de doublon.
2. Scanner le nouveau PDF ; comparer bénéficiaire, mentions et empreinte du fichier.
   Essayer un lien inconnu : aucun statut valide ni accès au dossier.
3. Révoquer avec le responsable affecté, puis ouvrir le même lien dans une autre
   session : statut révoqué immédiat. Répéter : motif et date initiaux conservés.
4. Corriger les critères, émettre une nouvelle attestation, remplacer l’ancienne.
   Vérifier les deux statuts et les deux fichiers conservés. Refuser un autre type,
   un autre dossier, un autre responsable ou une autre société.
5. Essayer les accès binaires directs, y compris avec jeton : pas de PDF ou de
   données privées pour un visiteur. Contrôler la page sur mobile et au clavier.
6. La suite cumulative découvre les tests P20 dans les huit configurations.
   Le parcours de mise à jour `p20` part de `92b0c3d` (#103/#104), compare les
   documents et preuves complets, puis conserve le nouveau registre après une seconde
   mise à jour et vérifie les transactions concurrentes réelles.
