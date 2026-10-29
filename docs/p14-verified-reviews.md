# P14 — Avis vérifiés et cas clients

Référence : [#37](https://github.com/Progideo/training_management/issues/37),
P14, EVA01, QUA01 et SEC02. Cadrage validé.

## Parcours

La coordination prépare une invitation depuis **Qualité → Avis et cas clients**,
avec une inscription, un programme actuellement public et une politique SEC02
approuvée. Le participant authentifié choisit son texte et son identité publique,
puis autorise la version exacte. Un modérateur explicitement habilité consigne
son contrôle du contenu, des identités de tiers et de la confidentialité avant
publication. Les retours S09 ne sont jamais repris automatiquement.

Pour un cas client, la coordination prépare le texte public et sa période,
écarte explicitement la confidentialité et désigne un représentant déjà habilité
sur le dossier P05. Sa qualité pour autoriser la publication porte une référence
privée explicite : une habilitation P05 seule ne vaut pas consentement.
Le représentant autorise le texte exact et, séparément, le nom demandé de
l’entreprise. La modération intervient ensuite. Aucun logo, citation nominative
ou résultat individuel n’est inclus dans cet incrément.

Les champs deviennent immuables dès la demande : une correction exige une nouvelle
version et un nouvel accord. Chaque demande, consentement, décision et retrait
conserve auteur, date serveur et contenu exact dans un historique privé.
Aucun groupe de modérateurs n’est attribué automatiquement. L’auteur ne reçoit
aucun droit ORM sur les publications ou leurs preuves ; son portail projette
uniquement les informations contrôlées de sa demande.

Les invitations utilisent la file native, un lien de connexion et un journal
unique par demande. Destinataire, adresse et accès sont revérifiés au transport.
Aucune copie de l’avis, du dossier ou de l’autorisation n’est envoyée par courriel.
Les publications sont consultables depuis la fiche publique du programme,
avec ou sans Website. Les dates publiques d’autorisation sont en UTC ; le mois
de participation provient de la date locale de la séance retenue.

Le retrait supprime immédiatement la projection et garde la preuve privée.
L’auteur peut retirer son accord après expiration de son accès pédagogique ;
ce droit ne rouvre aucun support ni dossier client. Un modérateur peut traiter
une demande externe avec motif. Les réponses publiques sont sans cache ;
l’application ne peut pas effacer les copies déjà faites par des tiers.
Aucune purge automatique ni durée de conservation présumée.

Depuis une fiche inscription, **Éléments de participation pour un avis** distingue
l’inscription, les présences actuelles et les attestations de participation
historiques. Ce diagnostic privé ne donne aucune autorisation de publication.

## Standard exact

Lecture de l’image Community `20.0-20261015`, [digest figé](ci.md).
`rating` et `portal_rating` sont présents, sous licence LGPL-3 ;
`website_rating` est absent. `rating.rating` conserve note, commentaire,
contact et jeton. Les routes `/rate/<token>` sont publiques ; la possession
du jeton ne prouve pas la participation Training Management. La soumission
native applique le retour à la ressource ; elle ne recueille pas les accords
distincts sur le texte et l’identité, ni une décision de modération P14.
`portal_rating` ajoute une réponse de l’éditeur, pas cette chaîne de consentement.

Sources : `rating/models/rating.py`, `rating/controllers/main.py`,
`rating/models/rating_mixin.py`, `portal_rating/models/rating_rating.py` et
`portal_rating/controllers/portal_rating.py`. Ne pas brancher les retours S09
sur ces routes publiques. Portal, QWeb, contacts et comptes existants permettent
une extension métier dans le socle, avec ou sans Website, comme P03/P04.

Reproduction : `python3 tests/ci/run_p14_native.py`, uniquement dans une base
jetable sur données fictives, transport interdit et transaction annulée.
La sonde vérifie la création sans rattachement pédagogique, l’absence d’accès
ORM portail, la mutabilité du commentaire et la remise à zéro du jeton/retour.
Elle ne prétend pas tester un parcours HTTP ni une publication Training Management.

Empreintes SHA-256 des sources Rating lues :

```text
6e8397fd66c8fa7cd3c76d3872464dc529fe3c2d0fdf0110e7f912f3ee51f176  models/rating.py
7d37a6020428229e0d4ace06b391ba3b38c32e69d422fb59aad18a5f6af55764  controllers/main.py
c025e3549c96b63c7739edd79875a1593bba5eb05bb7f79b027bd193edfd1bd5  models/rating_mixin.py
```

## Règles retenues

| Sujet | Règle | Exemple vérifiable / limite |
| --- | --- | --- |
| Participation vérifiée | Reprendre la règle de l’attestation de participation S08 : durée S07 validée strictement positive, revérifiée à l’invitation et à la publication. | Inscrit sans présence : refus. 30 minutes validées : admissible, sans présenter cela comme formation achevée. Une attestation antérieure ne remplace pas la vérification des présences actuelles. Le eLearning sans présence S07 attend un critère complémentaire explicite. |
| Identité d’un avis | Choix explicite du participant : « Participant vérifié » ou nom exact prévisualisé, avec accord distinct sur ce nom. | Aucun nom, employeur, photo, avatar, lieu ou groupe récupéré automatiquement pour l’affichage public. Le texte lui-même est contrôlé en modération pour les identités de tiers. |
| Contenu et consentement | Avis rédigé dans le portail authentifié sur invitation ; accord non précoché sur le texte final et son contexte public. | Texte, nom autorisé, formulation du consentement, auteur et date serveur sont figés. Un changement nécessite un nouvel accord. La satisfaction S09 reste privée. Aucun avantage ni obligation de répondre. |
| Modération | Groupe explicite de modérateurs, décision motivée et tracée sur le contenu consenti ; pas de réécriture silencieuse. | Coordinateur sans habilitation de modération : refus de publier. Le participant retrouve le statut et peut retirer son accord. |
| Cas client | Texte et contexte publics distincts du dossier privé, validés par un modérateur ; autorisation du représentant du client sur cette version exacte, avec preuve privée et périmètre explicite. | Le nom de l’entreprise nécessite une autorisation distincte ; aucun logo, citation nominative ni résultat individuel dans ce premier incrément. Un dossier confidentiel reste privé. |
| Affichage et retrait | Page publique du programme, contexte de formation approuvé, mois de participation et date de l’avis ; retrait immédiat de la projection, réponses HTTP sans cache. | Aucun nom de réalisation ou de client déduit du dossier. Retrait conservé dans l’historique privé ; une copie déjà faite par un tiers ne peut pas être effacée par l’application. |
| Conservation | Politique SEC02 explicitement approuvée avant invitation ou autorisation ; retrait public distinct d’une demande de suppression. | Aucune durée par défaut, purge automatique ou export public des preuves de consentement. |

La règle S08 figure dans `training_closure.py:_issue_certificate` :
elle additionne les minutes des présences actuellement validées et refuse
un total nul. L’inscription, l’ouverture d’accès, une réservation P13 ou un
score d’examen blanc ne constituent pas cette preuve.

## Recette cible

1. Contrôler inscrit seul, présence partielle validée, présence invalidée et
   eLearning sans présence ; aucune admissibilité inventée.
2. Inviter sur données fictives, rédiger et prévisualiser texte/contexte/identité ;
   vérifier accord explicite, absence de doublon et aucune diffusion S09.
3. Refuser publication non modérée, nom non autorisé et cas confidentiel.
   Tester participant, pair, client, modérateur et autre société, en accès direct.
4. Retirer puis recharger anonymement et avec un ancien lien ; vérifier historique,
   cache, doubles requêtes et concurrence entre publication et retrait.
5. Vérifier français, clavier et mobile ; installation vierge et deux mises à jour
   avec conservation des historiques et fichiers, avec et sans Website.

Les résultats réellement exécutés et la portée de chaque PR restent dans la PR.
