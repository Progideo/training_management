# S07 — Présences et émargement

Référence : [#17](https://github.com/Progideo/training_management/issues/17), PRE01–PRE03.

## Parcours

Le coordinateur configure la collecte papier, électronique ou mixte dans la séance
existante. La fenêtre électronique va du début de séance à 30 minutes après sa fin par
défaut, pour laisser confirmer un intervalle entièrement écoulé. Les marges
avant/après sont configurables. Le texte de confirmation est configurable. Les anciennes
séances ne reçoivent aucune présence inventée à la mise à jour.

Depuis « Mes formations », le participant authentifié déclare son propre intervalle
écoulé et accepte le texte affiché. Le serveur conserve identité, séance, texte,
méthode et date réelle de déclaration. Une déclaration tardive reste une anomalie
à expliquer au contrôle ; les intervalles futurs ou hors séance sont refusés.
Un lien collectif ne porte aucun droit de signature. Les accès S03 doivent être
actifs ; suspension, révocation, expiration ou annulation empêchent une déclaration.

Depuis ses séances affectées, le formateur contrôle les intervalles après la fin
de séance, valide séparément et peut constater une absence sans déclaration.
Il ne valide ni sa propre présence ni une déclaration dont il est l'auteur.
Le coordinateur importe un papier signé depuis la séance en indiquant la personne,
l'intervalle et la provenance ; ce dépôt attend le contrôle du formateur.
Un fichier collectif reste réservé aux coordinateurs de la société exploitante :
aucune diffusion aux autres participants ni au client.

Une ligne unique par inscription et séance porte la durée retenue. La dernière
validation ou correction fait autorité : les sources ne s'additionnent jamais.
90 minutes sur 120 donnent 90 minutes ; retard et absence restent distincts.
Une correction exige un motif et un justificatif, conserve avant/après, auteur,
date serveur et toutes les déclarations et pièces initiales. Aucun antidatage.
Les décisions périmées sont refusées avec demande de rechargement.

## Standard et sécurité

Vérification sur l'image Community `20.0-20261015` épinglée dans la CI :

| Standard vérifié | Usage / limite |
| --- | --- |
| `hr_attendance/models/hr_attendance.py` | Pointage et temps de travail d'un `hr.employee` ; imposer des employés aux stagiaires créerait un référentiel RH inadapté. |
| `event/models/event_registration.py` | Inscription et état de présence événement ; ne couvre pas les intervalles PRE01 et les déclarations/contrôles PRE02 par séance S04. |
| `portal`, `web`, ORM et QWeb | Authentification, formulaires CSRF, vues, assistants, règles de société et téléchargements natifs réutilisés. |
| `sign` | Absent de cette image Community ; aucune dépendance Enterprise ajoutée. |

Ajout ciblé dans le socle existant : ligne de présence et événements immuables,
sans autre application ni authentification. Pas de copie ou modification du cœur.
Les pièces sont des champs binaires natifs privés, sans pièces jointes publiques
ou jetons autonomes. Le contrôle natif de streaming et la politique documentaire
revérifient l'utilisateur réel ; pas d'envoi par messagerie. Les portails reçoivent
des valeurs explicitement sélectionnées, sans droits ORM généraux ni pièces collectives.
Le verrou et la révision S03 protègent les doubles déclarations et les suspensions
concurrentes ; la contrainte unique empêche un second compte de présence.

Le chargement des nouvelles vues sur une base équipée de Website réutilise le
pont de migration ciblé S05 : défaut de visibilité natif limité à la transaction,
puis restauration immédiate. Aucun changement de visibilité des vues existantes.

Ce dispositif constitue une déclaration et un contrôle interne. Aucune signature
dessinée ou certification juridique n'est ajoutée. L'asynchrone reste suivi par
les activités S05, sans séance fictive ; les attestations relèvent de S08.

## Recette courte

1. Créer une séance mixte de 120 minutes et régler la fenêtre et le texte.
2. Participant : déclarer 30 → 120, puis rejouer ; une déclaration, zéro minute
   validée avant le contrôle. Refuser accès d'un autre participant ou d'une autre société.
3. Formateur affecté : valider ; vérifier 90 minutes et 30 de retard. Tester
   absence, déclaration tardive avec explication, décision périmée et auto-validation.
4. Coordinateur : importer le papier de la même personne ; aucun cumul.
   Corriger avec justificatif ; vérifier les anciens fichiers et le journal inchangés.
5. Vérifier formulaire mobile, parcours clavier, CSRF, liens directs et jetons,
   refus des pièces collectives aux profils portail/commercial et hors société.
6. Exécuter `tests/ci/run_s07.sh` : S06 vers S07, historiques catalogue/documents/
   apprentissage/Survey, tests du socle et intégrations, installation vierge,
   deuxième mise à jour avec présences et deux transactions concurrentes.

Les résultats réellement exécutés sont consignés dans la PR et ses artefacts CI.
