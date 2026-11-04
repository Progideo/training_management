# Libellés français de recette

Référence : [#138](https://github.com/Progideo/training_management/issues/138).

Les pages de présence, signature personnelle, fiche catalogue et passation commune
renseignent le titre traduisible du layout natif. La confirmation dynamique
« absent » est traduite dans le contrôleur de son module avant sa projection
HTML ; aucun appel de traduction dépendant du contexte Python QWeb.
La réaffectation des contrôles référence explicitement ses vues dans le catalogue
français. Les autorisations, signatures et minutes validées restent inchangées.

Recette : ouvrir ces pages en français, choisir « Absent » puis revenir à
« Présent » ; vérifier le texte de consentement, le refus d’un formulaire périmé
et la validation séparée de chaque séance par son formateur. Le test des accès
natifs aux examens vérifie le refus final après l’éventuel renvoi de langue
standard Website.
