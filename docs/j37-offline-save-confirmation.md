# Reprise après coupure et fermeture du lecteur

La confirmation du serveur reste une sauvegarde réussie lorsque le cadre isolé
a été retiré après un échec de renouvellement. La file est vidée et le portail
invite alors à recharger le lecteur pour reprendre. Un message sans fenêtre
source ne peut pas être attribué au cadre retiré.

Recette : sauvegarder hors ligne, laisser échouer un renouvellement, rétablir
le réseau puis réessayer. Vérifier une seule écriture, la confirmation explicite
et la reprise de l’état enregistré après rechargement.
