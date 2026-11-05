# P11 — rejeu d’un retour sans pièce jointe

Référence : [TM #144](https://github.com/Progideo/training_management/issues/144).

La recette a créé deux retours fictifs identiques sans fichier. Le nom de fichier
absent peut être une chaîne vide dans un ancien retour ; la comparaison du rejeu
attendait `False`. La comparaison normalise cette absence, sans réécrire les traces.
Un texte différent reste un nouveau retour. Les contrôles de rôle et d’état,
les verrous et les pièces jointes restent ceux de P11.

Recette : sur une action fictive réalisée, le tuteur saisit deux fois le même
retour sans fichier. Un seul retour supplémentaire doit exister. Saisir ensuite
un texte différent et vérifier les auteurs, dates et textes conservés. Les deux
traces déjà créées pendant la découverte restent présentes.

Validation locale : neuf tests natifs P11 réussis, dont le nouveau cas sans
fichier, ses espaces périphériques et l’ajout d’un commentaire différent.
Les scénarios avec PDF restent couverts. Ruff contrôle et format réussis.
Contre-essai navigateur après livraison requis.
