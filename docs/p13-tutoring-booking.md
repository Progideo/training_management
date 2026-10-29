# P13 — Réservation de tutorat

Référence : [#36](https://github.com/Progideo/training_management/issues/36),
PED02 et P13 (§22) de la spécification v2. **Cadrage validé** ;
le tutorat privé PED02 déjà livré reste disponible.

## Standard exact et choix retenu

Sources lues dans l’image Community `20.0-20261015`, paquet `20.0.20261015`,
digest [figé par la CI](ci.md). Calendar et Resource sont LGPL-3.

| Besoin | Couverture vérifiée et réalisation |
| --- | --- |
| Événements et invitations | `calendar.event` existe ; `appointment` est absent de l’image. Le standard ne relie pas une réservation au quota d’une inscription Training Management. |
| Disponibilités | `resource.calendar._work_intervals_batch` calcule horaires moins absences pour les ressources ; il ne confirme pas une réservation pédagogique. S04 possède déjà les séances, salles et indisponibilités des contacts formateurs. Réutiliser ce planning et son verrou société. |
| Confidentialité collective | Un événement privé masque les autres invités lors de la lecture ORM portail, comportement à conserver si Calendar est retenu. Les invitations et fichiers iCalendar auraient aussi besoin d’une recette propre. L’agenda métier proposé évite cette deuxième diffusion. |
| Agenda et synchronisation | Vue calendrier Odoo sur les créneaux Training Management ; aucune copie dans `calendar.event` ni synchronisation extérieure pour cet incrément. Aucun service, compte ou addon supplémentaire. Les engagements extérieurs doivent être signalés dans les indisponibilités S04. |
| Quota et capacité | Extension métier ciblée : créneaux par réalisation, droit de réservation par inscription, réservations individuelles conservées. Les contacts, comptes et accès existants restent les références. |
| Notifications | File native `mail.mail`, courriel individuel générique avec lien authentifié ; recontrôle des droits au transport, sans liste de pairs ni contenu pédagogique. |

Preuves de source : `calendar/models/calendar_event.py:255–269,891–927`,
`calendar/security/ir.access.csv:6–8`,
`resource/models/resource_calendar.py:525–542` dans l’image figée.
La sonde [p13_native_coverage.py](../tests/probes/p13_native_coverage.py)
reproduit deux événements superposés acceptés et le masquage des autres invités
pour un compte portail invité à un événement privé, sur une base fictive avec Calendar.
Ce constat ne prouve aucune réservation P13 déjà opérationnelle.
Reproduction locale avec Docker : `python3 tests/ci/run_p13_native.py`.
Le lanceur utilise l’image figée, un PostgreSQL séparé et des identités fictives,
sans transport ; il annule les écritures puis supprime ses propres ressources.
Cette sonde d’architecture ne remplace pas la suite cumulative métier.

## Règles

La coordination définit un droit pour une inscription : nombre positif de réservations
incluses, référence de prestation et politique de conservation approuvée.
Aucune valeur commerciale n’est préremplie. Une confirmation consomme une unité,
quelle que soit la durée du créneau, annoncée avant réservation. Le droit convenu
est conservé sans modification ; sans droit, aucune réservation autonome.

Le créneau porte réalisation, tuteur existant, début et fin, mode individuel ou
collectif, capacité et conditions d’annulation. Le participant ne voit que les
créneaux de sa réalisation pour son tuteur affecté, compris dans sa période d’accès
autorisée ; il ne voit aucun autre inscrit. Le tuteur consulte ses rendez-vous dans
le même portail, avec les seuls participants actuellement affectés.
Individuel signifie capacité un. Les instants UTC et les heures locales suivent
les conventions et contrôles de fuseau S04. Une réservation ne constitue ni une
présence ni une progression pédagogique.

La restitution est explicitement activée ou désactivée par la coordination.
Si elle est activée, un délai en heures avant début doit être renseigné :
annuler au plus tard à cette échéance restitue une unité ; après cette échéance,
le quota reste consommé. L’annulation libère toujours la place avant le début.
Une annulation de créneau par la coordination restitue les unités de toutes ses
réservations. Conditions et règle appliquée restent figées avec chaque confirmation.
Une politique modifiée ne réécrit pas les réservations antérieures.

Les opérations serveur revérifient accès actif, société, inscription, tuteur,
période, capacité et quota. Verrous et révisions suivent l’ordre société,
réalisation, inscription, créneau. Deux confirmations concurrentes ne dépassent
ni le quota ni la capacité. Rejouer une confirmation ou une annulation conserve
une seule opération et ses notifications. Une réservation annulée reste consultable ;
une nouvelle réservation exige une nouvelle intention explicite.

Les créneaux publiés, leurs auteurs et dates de publication/annulation sont conservés.
Un horaire déjà réservé
ne se déplace pas silencieusement : annuler puis proposer un remplacement.
Une suspension ou réaffectation retire les accès selon S05, sans effacement
ni restitution commerciale inventée. Le participant annule avant le début du
créneau ; après le début, il contacte la coordination. Aucun accès au commanditaire
par défaut. Les réservations ne portent aucune pièce jointe partageable.

## Recette courte

1. Configurer explicitement quota, restitution et délai sur données fictives.
   Publier un créneau individuel et un collectif ; contrôler durée, fuseau,
   disponibilité et conditions visibles avant confirmation.
2. Réserver depuis un compte participant : une unité consommée et notifications
   privées au participant et au tuteur. Rejouer : aucun doublon. Refuser quota
   épuisé, créneau complet, pair, autre client, autre société et accès suspendu.
3. Soumettre réellement deux transactions sur la dernière place et le dernier
   quota ; vérifier l’unique confirmation après reprise de transaction.
4. Annuler avant/après échéance, avec et sans restitution ; rejouer. Annuler le
   créneau par coordination. Contrôler les historiques et notifications.
5. Vérifier conflits avec séances et indisponibilités S04, dates jointives,
   changement de fuseau, mobile/clavier et accès directs.
6. Installer à neuf puis mettre à jour deux fois une base fictive avec historiques,
   supports et PDF conservés. Vérifier les notifications sans transport réel.
