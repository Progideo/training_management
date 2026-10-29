# P03–P04 — catalogue public et démonstration

La [matrice C02/C04](p01-p06-coverage.md) qualifie l’existant et les écarts.
La fiche `/formations` utilise Portal/QWeb sans imposer Website/eLearning.
Avec Website, la société du site borne le catalogue ; sans Website, la société
courante borne la projection. Les visiteurs n’obtiennent aucun droit ORM métier.

Sur un brouillon, le coordinateur renseigne les compléments P03 et coche
l’approbation publique. Validation puis publication figent le contenu, l’extrait
PDF et les questions de démonstration. Les informations manquantes sont affichées
comme non confirmées dans la fiche et le PDF. Les versions déjà validées gardent
leur PDF historique ; créer une nouvelle version pour enrichir leur programme.
La distinction entre examen blanc et certification officielle figure dans les
rubriques consacrées aux examens, sans avertissement générique en tête de fiche.

Le PDF du programme est servi par une route publique dédiée qui vérifie la
publication, la société et l’empreinte. La pièce jointe reste privée dans Odoo.
L’extrait est une copie explicitement destinée à la publication, séparée des
supports privés S05. Les questions de démonstration ne référencent ni Surveys,
ni banque d’examen, ni tentative, ni résultat ou progression.
La correction est calculée à la demande sans persistance.

## Recette courte

1. Créer un programme avec résultats, exercices/livrables, profils, durée d’accès,
   inclusions, préparation, examen blanc et statut explicite de l’examen officiel.
2. Ajouter un extrait PDF et des questions de démonstration. Approuver la diffusion
   publique, valider puis publier ; comparer version, modalités et inclusions du
   PDF et de la fiche. Vérifier les informations non confirmées et le texte qui
   distingue examen blanc et certification officielle.
3. En visiteur, rechercher par texte/catégorie/modalité ; télécharger le programme
   et l’extrait, répondre au mini-quiz et lire la correction. Vérifier qu’aucune
   inscription, tentative ni progression n’a été créée.
4. Tester les liens directs d’un brouillon, d’une autre société et d’un PDF privé :
   refus. Retirer le programme : ses routes publiques deviennent indisponibles.
5. Modifier une question ou un champ après validation : refus. Créer une nouvelle
   version ; vérifier que le PDF précédent est inchangé et l’approbation publique
   doit être renouvelée.
