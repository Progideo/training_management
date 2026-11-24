# Modèles d’email des formations

Décision du 24 novembre 2026 : tous les emails des modules training passent par des
modèles Odoo standard (`mail.template`), rédigés en anglais et traduits en français.

## Règles

- Chaque journal d’envoi (inscription, espace formation, mise en pratique, tutorat, retours,
  publication, alerte de l’équipe, alerte de dates, convocation, accusé de demande) a son
  modèle, modifiable dans Paramètres > Technique > Modèles d’email.
- Le modèle ne fournit que l’objet et le corps. Destinataire, copies, pièces jointes,
  rapports et abonnés restent fixés par le journal ; l’expéditeur suit l’identité de la
  société (`training_notification_template_id`).
- Les textes restent génériques : aucun nom, titre privé, résultat ni fichier ; un lien vers
  l’espace authentifié.
- Le journal conserve une empreinte de l’objet et du corps mis en file : un email modifié
  après sa mise en file est refusé au transport, comme les droits du destinataire.
- La langue est celle du destinataire, enregistrée dans le journal.
- Les modèles sont chargés une seule fois (`noupdate`) : une adaptation propre à un
  organisme (texte, cadre) se fait dans Odoo ou dans un module séparé.

## Recette courte

1. Modifier l’objet du modèle « Training: enrollment update », puis ouvrir l’accès d’une
   inscription : l’email en file reprend le nouvel objet.
2. Participant en français : objet et corps en français.
3. Modifier le corps d’un email en file, puis lancer l’envoi : refusé.
