# S03 — Réalisations, places, inscriptions et accès

Références : [besoin #13](https://github.com/Progideo/training_management/issues/13),
[pilotage #3](https://github.com/Progideo/training_management/issues/3),
[architecture et comptes #8](https://github.com/Progideo/training_management/issues/8),
[S02 #12](https://github.com/Progideo/training_management/issues/12).
La spécification v2, §2 et INS01–INS05, définit le besoin ; SEC01 et CAT02
s'appliquent dès cet incrément. L'import documentaire de référence a été conservé, actualisé et fusionné via
la [PR #41](https://github.com/Progideo/training_management/pull/41), après revue
le 22 octobre 2026. Voir l’[index des références](README.md). Les empreintes de la spécification et du prompt maître sous
`sources/` correspondent à cet import. Aucun fichier synchronisé n'est modifié.
L'audit historique Odoo 19 reste suspendu.

## Décision approuvée le 22 octobre 2026

Après validation du périmètre, l'utilisateur a validé le modèle dédié, sans
dépendance obligatoire à Événements, puis le développement en branche et une
PR à revoir. Aucune fusion, aucun déploiement, aucune intervention neopro_dev ou
production et aucune migration réelle ne sont autorisés par ces validations initiales.

Après traitement de #41, l’utilisateur a autorisé le 22 octobre 2026 la fusion
et le déploiement S03 sur la cible de développement habituelle `neopro_dev`.
La répétition sur copie isolée, les sauvegardes et les contrôles de conservation
précèdent la bascule ; les résultats effectifs sont consignés dans la PR #46.
La production et une migration Odoo 19 restent hors périmètre.
La réorganisation/parallélisation de CI est prévue dans une prochaine PR ([#47](https://github.com/Progideo/training_management/issues/47)).

Le socle `training_management` passe en `20.0.1.1.0` ; l'intégration
`training_management_sale` en `20.0.1.9.0`. Le premier reste dépendant de `base`
seulement ; le second conserve ses dépendances S02. Pas de nouvel addon ni de
copie de module standard. Le code conserve LGPL-3.0-only, manifest LGPL-3.

## Étude de la distribution exacte

Sources extraites hors Git de l'image déjà utilisée pour S02 :
`odoo@sha256:61e3c71b0503c5f658e604c3e340bede20b97d05f726179fa006eae50a32fd23`.
`release.py` déclare `20.0-20261015` et la provenance Community
`49529f034a60e4e9838e08e0a5616e5f2f38c601`. Il ne s'agit pas d'une comparaison
exhaustive avec le dépôt amont. Les empreintes de `release.py`, des trois
fichiers `event_sale/models/{sale_order,sale_order_line,event_registration}.py`
et de `website_sale_slides/models/sale_order.py` correspondent aux empreintes
conservées dans [s02-native-coverage.md](s02-native-coverage.md).

| Standard lu | Couverture réelle et écart S03 |
| --- | --- |
| `event/models/event_event.py` | Dates obligatoires, capacités et fuseaux ; adapté aux événements datés, hypothèses à modifier pour l'autonome. |
| `event/models/event_registration.py` | Inscriptions sans nom possibles ; états draft/open/done/cancel, identité du contact ayant réservé. Pas le cycle complet d'admission et d'accès. |
| `event_sale/models/sale_order_line.py:_init_registrations` | Nombre d'inscriptions fondé sur la quantité commerciale ; un forfait S02 de quantité 1 n'est pas un effectif de 10. |
| `event_sale/models/event_registration.py` | Recalcul de l'état à partir de la commande, contact repris depuis le client commercial. |
| `event/security/ir.access.csv`, `event_sale/security/ir.access.csv`, portail `/my/events` | Lecture par contact ayant réservé ou client de la commande ; ne démontre pas le mandat nominatif requis pour les données de formation. |
| Capacités Événements | Comptage des inscriptions actives open/done ; pas de verrou explicite dans le chemin de contrôle examiné. Aucun dépassement concurrent du standard n'a été reproduit dans cette étude. |
| `event_product`, `event_sale`, `website_event_sale` | Ponts auto-installables selon leurs dépendances. Leur installation n'est pas neutre sur une base équipée. |
| `website_sale_slides/models/sale_order.py:_action_confirm` | Ajout de l'acheteur aux cours liés : ne doit pas ouvrir les formations gérées sans admission explicite. |

La configuration ne suffit pas. L'héritage d'Événements nécessiterait de revoir
plusieurs mécanismes centraux : dates, identité, états, places, portail et pont
commercial. Le modèle dédié représente les trois objets validés sans ajouter un
second référentiel de contacts, de ventes, de comptabilité ou d'authentification.
Une éventuelle intégration Événements ultérieure devra conserver ce registre
unique ; elle n'est pas livrée ici. Les manifests standard examinés déclarent
LGPL-3. L'étude du standard est une lecture de code, distincte des tests du module.

## Modèles et règles

- `training.delivery` : réalisation datée ou offre autonome, société exploitante,
  version de programme, responsable, fuseau, capacité et seuil d'ouverture.
  L'autonome ne porte pas de dates de session fictives. La version, les dates et
  la politique d'accès sont figées dès qu'il existe des lots ou inscriptions.
- `training.seat.allocation` : lot client, référence unique par réalisation,
  quantité positive, échéance obligatoire, état réservé/confirmé/expiré/annulé.
  La réservation occupe la capacité tant qu'elle n'est pas expirée ; un lot
  confirmé conserve ses places jusqu'à libération explicite.
- `training.enrollment` : participant `res.partner`, réalisation et programme,
  lot ou gratuité motivée, compte personnel Odoo éventuel, admission, périodes
  et autorisation commerciale. Une seule inscription non terminale par personne
  et réalisation, sans rapprochement automatique des homonymes.
- `training.operation` : journal append-only des valeurs avant/après, auteur
  réel, date serveur et motif. La vue présente les libellés métier et le nom du
  dossier capturé lors de l'opération. Les JSON restent des preuves internes.

### Décompte et engagement commercial

Un lot de 10 places occupe 10 places, même avec 7 participants nommés : il reste
3 places à désigner. La nomination ne consomme pas une deuxième fois la capacité.
Une invitation gratuite réservée ou confirmée consomme une place directement.
Les demandes et personnes en attente ne consomment pas de capacité.

La ligne commerciale doit être accessible avec les droits natifs Ventes ; le
rôle de coordination ne les attribue pas. Le client exact, la société et le
programme doivent correspondre. L'engagement du lot exige une commande confirmée.
L'effectif contractuel explicite de S02 fait autorité pour les tarifs personne
et forfait ; plusieurs lignes d'une même commande ne le multiplient pas.
Les lots vivants, y compris réservés, sont additionnés entre réalisations pour
éviter de réutiliser le même engagement commercial. Aucun paiement n'est créé.

Une référence de réservation ne peut pas être réutilisée sur la même réalisation.
Les confirmations répétées restent idempotentes. La liste d'attente est ordonnée
par date serveur puis identifiant ; le coordinateur propose une place avec une
nouvelle échéance, sans promotion automatique. Sous le seuil d'ouverture, la
confirmation de la réalisation exige un motif. Les seuils et délais restent à
renseigner ; aucune durée d'accès métier ni condition d'annulation financière
n'est inventée.

L'expiration est vérifiée dans les décisions et calculs à l'heure serveur,
indépendamment d'un cron. L'action « Constater l'expiration » matérialise ensuite
la transition et son historique. L'état persistant peut donc rester « Réservée »
après l'échéance, sans conserver la place ; l'échéance figure sur le dossier.

### Admission et accès

La confirmation nominative exige identité, origine commerciale ou gratuité,
prérequis validés ou dérogation motivée et place disponible. La décision de
prérequis est enregistrée ici ; le positionnement détaillé et les aménagements
confidentiels restent dans S04.

L'accès exige en plus l'autorisation commerciale manuelle motivée, un compte
personnel actif et une période ouverte. Le paiement différé B2B peut être
explicitement autorisé. Commande confirmée, règlement, avis de virement et
habilitation documentaire S02 ne produisent pas ces décisions.

La période est fixe ou calculée lors de la première activation explicite. Une
répétition ou une reprise après suspension ne remet pas le compteur à zéro.
Une prolongation est motivée et ne réécrit pas les anciennes dates du journal.
Une révocation est définitive pour cette inscription. Retirer l'autorisation
commerciale bloque l'accès effectif. Désactiver le compte personnel le bloque
également. Les vues calculées reflètent le temps lors d'une nouvelle lecture ;
le futur consommateur doit appeler le contrôle serveur courant, sans se fier
à un ancien badge d'interface.

`_effective_state()` est le point de contrôle privé à utiliser par les futures
intégrations après leur contrôle d'identité et d'habilitation. S03 ne livre ni
accès aux PDF, ni examens, ni portail participant. Le contrôle des fichiers et
routes devra être prouvé dans S05/S06, y compris expiration et révocation.
Documents délivrés et contenus pédagogiques gardent des politiques distinctes.

### Annulation, report et remplacement

Les annulations révoquent l'accès et conservent les dossiers. Le remplacement
lie l'ancienne inscription à une nouvelle personne dans la même réalisation et
le même lot. Le report lie le même participant à une nouvelle réalisation.
La cible demeure une nouvelle demande ; prérequis, autorisation commerciale,
période, résultats et comptes ne sont pas copiés automatiquement.

La place nominative libérée revient au lot. Pour libérer aussi la capacité
globale et réaffecter l'engagement commercial, le coordinateur réduit explicitement
le lot après les changements nominatifs, ou l'annule entièrement. Une réduction
ne peut pas passer sous le nombre de places nominatives encore occupées. Les
valeurs avant/après et le motif sont conservés. Cela ne modifie ni commande,
ni facture, ni avoir, ni paiement. Une commande avec des lots vivants ne peut
pas être annulée avant leur traitement explicite. Son identité et son effectif,
ainsi que les lignes commerciales déjà référencées, sont protégés des réécritures.

## Sécurité et concurrence

| Profil | Droits S03 |
| --- | --- |
| Coordinateur | Gestion des réalisations, places et admissions dans ses sociétés ; journal en lecture seule. |
| Coordinateur + Ventes explicitement attribué | Même périmètre S03 et utilisation des sources commerciales autorisées par les droits natifs. |
| Commercial seul, facturation seule, lecteur catalogue, interne sans rôle | Aucun accès aux dossiers S03 ; aucune activation pédagogique. |
| Portail participant/représentant, public | Aucun accès aux modèles S03 à ce stade. Les futurs portails restent S05/P05. |

Les champs générés, états et horodatages ne sont pas modifiables directement.
Les valeurs de contexte ne permettent pas d'injecter une admission ni une société
étrangère. Les suppressions métier sont refusées ; les historiques restent liés.
L'export conserve les restrictions société et nécessite le droit natif d'export,
non attribué automatiquement. Aucun chatter ni envoi spécifique n'est introduit.

Les opérations critiques verrouillent la réalisation avec `lock_for_update()`
et écrivent une révision technique avec l'ORM. Cette écriture force le rejet
d'une ancienne photographie REPEATABLE READ après un engagement concurrent.
Les sources commande et ligne ont également une révision technique. Ces champs
ne sont pas des compteurs métier et ne sont pas modifiables par API publique.
Les savepoints rendent les refus atomiques, y compris si l'appelant les intercepte.
Aucun commit métier manuel ni SQL métier n'est ajouté.

Deux usages bornés de `sudo()` : ajout d'une ligne de journal serveur après
contrôle de coordination/société ; recherche d'existence de lots pour protéger
une modification commerciale sans ouvrir ces dossiers au commercial.
Les sondes de tests peuvent commettre leurs seules données fictives sur les bases
jetables dont le préfixe est contrôlé ; elles refusent neopro_dev et la production.

## Installation et mise à jour avec Website

L'installation sur base vierge utilise la commande native `-i` ; pas de dépendance
artificielle à Website. La mise à jour depuis S02 sur une base déjà équipée de
Website reproduit le défaut de chargement partiel connu de S01 : insertion d'une
nouvelle vue avant disponibilité du défaut obligatoire `ir.ui.view.visibility`.

La recette S03 charge les XML nouveaux avec `odoo.tools.convert.convert_file`
dans le registre complet, puis effectue la mise à jour native. Le script
`tests/probes/s03_view_bootstrap.py` rend cette procédure reproductible sur les
seules bases jetables. Aucun patch du cœur, défaut de colonne ou retrait de
contrainte SQL n'est introduit. La CI applique cette étape avant la transition
historique S02 → S03. Un futur déploiement devra répéter cette procédure sur une
copie autorisée et prévoir sauvegarde/retour arrière ; il exige une autorisation
distincte et n'est pas effectué par cette PR.

## Recette courte à revoir

Utiliser seulement des données fictives et des comptes réellement restreints.

1. Coordinateur : créer une offre autonome, puis une session datée. Choisir V1
   validée et conserver ce programme après création de V2.
2. Coordination + Ventes : rattacher un forfait confirmé de 10 personnes, quantité
   commerciale 1. Réserver/confirmer le lot, nommer 7 personnes : 3 places libres
   dans le lot, 10 places occupées globalement. Refuser dépassement et doublon.
3. Sans prérequis, refuser l'admission. Valider ou déroger avec motif, confirmer
   deux fois sans doublon. Vérifier que la vente seule n'a ouvert aucun accès.
4. Sur décision B2B différée motivée, autoriser puis activer un compte portail
   personnel. Vérifier dates fixes/durée, début futur, expiration, suspension,
   retrait d'autorisation, désactivation du compte et prolongation motivée.
5. Proposer une place à la première demande en attente avec délai explicite.
   Dépasser l'échéance : place libérée sans attendre un cron, admission refusée.
6. Remplacer puis reporter vers une nouvelle demande. Conserver ancien dossier et
   journal ; vérifier qu'aucun résultat, accès ou autorisation n'est transféré.
   Libérer explicitement les places du lot si l'engagement doit être réaffecté.
7. Commercial/facturation seuls, deux portails, public et lecteur : refuser les
   lectures et méthodes S03. Coordinateur d'une seule société : refuser lecture,
   export et écriture de l'autre société. Vérifier les documents S02 séparément.
8. Contrôler les formulaires et assistants en français ; relire le journal.
   Réaliser la recette navigateur manuelle, y compris confort mobile/clavier,
   avant une ouverture d'exploitation. Les tests Form ne valent pas cette recette.

Les résultats exécutés et leurs limites sont conservés dans la PR et les journaux
CI. Le suivi humain de validation reste distinct des tests automatiques.

## Hors périmètre conservé

S04 : planning des séances, ressources, positionnement détaillé et adaptations.
S05/S06 : portail participant, PDF privés, progression, tutorat et examens.
S07/S08 : émargement et documents de clôture. P05 : portail entreprise et mandats.
M01 : reprise Odoo 19. Les relevés et imports bancaires restent reportés et non
validés ; les encaissements manuels S02 et leurs garde-fous restent applicables.
Aucun paiement en ligne, remboursement automatique ou changement de production.
