# Libellés français et navigation des questionnaires

Références : [#138](https://github.com/Progideo/training_management/issues/138),
[#140](https://github.com/Progideo/training_management/issues/140),
[#141](https://github.com/Progideo/training_management/issues/141).

Les pages de présence, signature personnelle, fiche catalogue et passation commune
renseignent le titre traduisible du layout natif. La confirmation dynamique
« absent » est traduite dans le contrôleur de son module avant sa projection
HTML ; aucun appel de traduction dépendant du contexte Python QWeb.
La réaffectation des contrôles référence explicitement ses vues dans le catalogue
français. Les autorisations, signatures et minutes validées restent inchangées.
Les espaces de suivi, tutorat, réclamations, documents, dossiers d’entreprise,
évaluations et satisfaction utilisent le même mécanisme de titre natif.

Recette : ouvrir ces pages en français, choisir « Absent » puis revenir à
« Présent » ; vérifier le texte de consentement, le refus d’un formulaire périmé
et la validation séparée de chaque séance par son formateur. Le test des accès
natifs aux examens vérifie le refus final après l’éventuel renvoi de langue
standard Website.

Les liens vers un examen partagé et sa version initiale imposent le formulaire
Survey natif enrichi. Les actions d’ouverture des questionnaires de positionnement,
d’acquis et de satisfaction imposent aussi ce formulaire : une autre vue primaire
de Survey ne doit pas détourner la navigation vers un diagnostic. La création
d’une version conserve les définitions publiées et les tentatives antérieures.

Recette complémentaire : publier une nouvelle version, suivre « Examen initial »,
puis ouvrir les questionnaires dédiés et vérifier leurs questions et commandes.

Les dates des notifications du bilan utilisent le format datetime natif Odoo.
Les fractions de seconde techniques de `create_date` restent dans le journal
original ; elles ne doivent pas faire échouer la présentation du portail.
Ouvrir un bilan coordinateur avec des notifications et vérifier ses indicateurs,
sa liste de notifications et l’absence de mise en cache privée.
