# Accès aux examens et continuité des dossiers

Corrections de S05/S06, S08 et P20 avant recette finale.

## Règles

- L’expiration seule conserve l’historique d’examen. Le retrait d’autorisation,
  la suspension et les autres blocages effectifs retirent aussi les corrigés,
  images et entrées d’historique. Les droits restent contrôlés à chaque accès.
- Le critère de progression par examen est proposé avec l’intégration Surveys.
  Il exige une version publiée du même programme. Le serveur refuse une activité
  sans examen ou le retrait de son examen. Les anciennes configurations incomplètes
  sont conservées à la mise à jour ; les corriger avant utilisation. Une nouvelle
  dépendance ne peut pas les rendre bloquantes. La dépendance Surveys des retours
  de satisfaction est annoncée dès le formulaire.
- Le coordinateur peut **réaffecter le responsable qualité**, avec un motif,
  même après émission ou clôture. Le successeur doit être actif, habilité qualité
  et autorisé dans la société exploitante. Les anciens auteurs et la politique de
  conservation restent inchangés. L’ancien responsable perd ses droits sur le dossier.
- Le responsable qualité affecté peut **rectifier un dossier clôturé**, avec un
  motif. Cette action le rouvre pour utiliser les versions de preuves et les
  émissions S08 existantes. Les preuves validées, anciens PDF et décisions de
  vérification restent conservés. Ajouter les preuves corrigées, les valider,
  émettre le nouveau document puis remplacer explicitement l’ancien avec P20.
  La réouverture seule ne révoque aucun document. Clôturer à nouveau après contrôle.
- L’historique privé conserve chaque réaffectation, réouverture et clôture avec
  auteur et date. La dernière clôture reste affichée pendant la rectification.
  Une clôture antérieure à cette évolution est conservée dans les métadonnées du
  dossier et rappelée lors de sa première rectification ; aucun historique inventé
  n’est créé à la migration. Les répétitions ne créent pas de doublon et un ancien
  formulaire ne peut pas rouvrir une clôture ultérieure.

## Recette courte

1. Terminer un examen. Expirer les accès : historique lisible, nouveau départ
   refusé. Retirer l’autorisation : historique, corrigé et image refusés.
2. Sans Surveys, vérifier l’absence du critère d’examen. Avec Surveys, essayer de
   créer une activité sans examen puis de retirer l’examen d’une activité valide.
3. Émettre une attestation et clôturer. Archiver le responsable, réaffecter depuis
   la coordination, puis révoquer avec le successeur. Vérifier l’historique et les
   refus pour l’ancien responsable, un portail et une autre société.
4. Rectifier un dossier clos, ajouter une nouvelle preuve, émettre et remplacer
   l’attestation, puis clôturer. Comparer les anciens fichiers et leurs auteurs.
   Vérifier les deux liens publics et refuser un formulaire de rectification périmé.
