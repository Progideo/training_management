# Retrait des ressources communes

Le retrait motivé d’une version interactive appelle un point d’extension privé dans
la même transaction. Une erreur de l’application consommatrice annule le retrait.
La bibliothèque ne dépend d’aucune application pédagogique. Chaque adaptateur
avertit ses propres accès actifs. TM conserve son journal natif de notification
et crée une activité pour le responsable de la réalisation concernée ; les
preuves et acquis restent conservés.

Le moteur commun conserve une seule tentative active par personne, famille et
contexte. En cas de lancement concurrent sur le même contexte, une collision de
l’index actif déclenche une reprise native Odoo dans une transaction neuve. Les autres
contextes peuvent démarrer en parallèle ; le verrou éditorial reste partagé en
lecture et exclusif lors d’une modification.

## Recette

Retirer une version publiée avec un gestionnaire de bibliothèque. Vérifier le
motif, le refus des lecteurs et l’appel aux consommateurs. Faire échouer cet appel
et vérifier l’absence de retrait partiel. Lancer deux requêtes simultanées dans le
même contexte : une seule tentative et une reprise identique. Répéter dans deux
contextes distincts : deux tentatives indépendantes.
