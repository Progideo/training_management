# J21 — Frontières dans la composition complète

La qualification finale sélectionne les tests des dix addons ensemble, ainsi que
l’intégration fiscale régionale optionnelle lorsqu’elle est présente. Les briques
communes restent testées séparément sans applications métier.

Le rôle d’auteur de bibliothèque n’accorde aucun rôle TM ou eLearning. La présence
des modules standards `website_slides` ou `survey` peut toutefois permettre à un
utilisateur interne de rechercher des objets standards publics. Exiger une erreur
sur toute recherche vide de ces modèles ne démontre pas l’isolation des dossiers
privés et contredit leur fonctionnement natif.

Le test de bibliothèque conserve le contrôle de ses dépendances, des refus TM et
de l’absence de droits de conception ou d’administration. Lorsqu’un adaptateur
est installé, il crée un cours ou examen privé réel avec son auteur habilité,
puis vérifie que le simple auteur de bibliothèque ne peut ni le lire ni le
retrouver par recherche. Aucune autorisation de production n’est élargie.

La qualification complète et les preuves de conservation/restauration sont portées
par la composition épinglée dans le dépôt eLearning. Aucun déploiement ne résulte
de cette correction de test.

## Réconciliation avec la génération déjà livrée

La branche de séparation partait de `9c9fdcd0...` ; la génération encadrée
`616d2a342540eb7a7dbb8e48d6ecd084bc2fc926` contenait des correctifs supplémentaires.
Ils restent la référence de non-régression : demandes publiques bornées (#119),
réémission après révocation erronée, contrôle d’émargement délégué, retrait des
marges sans effet (#121) et réponses d’examen parallèles.

Les correctifs encadrés sont réintégrés sans rétablir une dépendance métier de
l’application autonome. Le verrou partagé de la famille et les reprises de requête
sont portés dans le moteur et le lecteur communs ; le verrou propre à l’inscription
reste dans l’adaptateur TM. Les nouveaux contextes et index d’unicité sont conservés.
Les activités formatives exclues ne deviennent pas des obligations d’attestation.

La migration `20.0.3.0.4` permet aussi la mise à jour des branches de séparation
qui portaient encore les anciennes marges retirées. Elle libère uniquement les
vues natives concernées avant leur rechargement ; les preuves d’émargement et
l’historique des réaffectations sont conservés. Aucun nouveau retrait fonctionnel
n’est décidé par cette réconciliation.
