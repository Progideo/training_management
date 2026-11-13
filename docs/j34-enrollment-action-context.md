# Contexte des actions du menu inscription

Les actions de report, remplacement et décision motivée ajoutent leur opération au contexte courant. Elles conservent la langue, la sélection de sociétés et les autres paramètres transmis par Odoo.

Les traductions Python de l’état « À venir », de la relance d’inactivité et de trois erreurs de contrôle portent aussi leur marqueur de catalogue. Leur texte français existant doit être chargé pour les appels serveur, y compris lorsque la même entrée sert une vue.

Recette : sous coordination en français, ouvrir un remplacement puis un report depuis le menu Actions. Vérifier le titre français et l’opération sélectionnée, puis annuler sans modification. Une société non autorisée doit rester refusée.
