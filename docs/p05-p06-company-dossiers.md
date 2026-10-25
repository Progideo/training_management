# P05–P06 — portail entreprise et versions intra

Références : #27, #28 et [matrice C02/C04](p01-p06-coverage.md).

## Habilitation et suivi

Le coordinateur crée une habilitation pour un compte portail Odoo existant,
une société exploitante, une entité commerciale cliente et des lots de places
explicitement choisis. Il la confirme ; auteur/date de confirmation et de
révocation sont conservés. Une habilitation confirmée ne change plus de périmètre :
révoquer puis remplacer. Aucune habilitation n’est créée par la reprise ou déduite
d’un nom, d’un domaine email ou du rattachement d’un contact.

Dans l’image exacte `20.0-20261015`, `res.partner.is_company` est calculé à partir
de l’entité commerciale et de l’identification fiscale. Ce champ ne conditionne
pas le droit métier P05 : le client est le contact racine de l’entité commerciale
native, désigné explicitement. Aucun identifiant fiscal supplémentaire n’est exigé.

Le portail `/my/company-trainings` affiche les demandes CRM qualifiées sur cette
entité et cette société exploitante, puis les dossiers des lots habilités. Les
PDF commerciaux restent soumis aux contacts nommés de S02.1. Les pièces de la
demande CRM restent internes ; le coordinateur diffuse les documents client
approuvés dans le dossier du lot.

Pour chaque lot, le représentant voit les séances, les noms et statuts des
participants de ce lot, ses nominations et les PDF explicitement diffusés.
Réponses, scores, positionnements, adaptations personnelles et tutorat ne sont
pas projetés. Les nominations ne créent ni contact, ni utilisateur, ni inscription.
La coordination traite la proposition dans le circuit d’inscription existant,
puis peut y rattacher l’inscription du même lot. L’activation pédagogique reste
une décision séparée de S03. Répéter la même nomination retrouve la proposition.

## Versions du dossier intra

Une version client appartient à une réalisation intra dédiée à une seule entité
cliente. Elle conserve sa référence au programme standard, ses objectifs client,
cas métiers, consignes et éventuel PDF confidentiel. Elle ne modifie ni le catalogue
ni les adaptations individuelles S04.

La soumission fige son contenu. Le représentant habilité peut enregistrer son
accord depuis le portail sur cette version précise ; le coordinateur peut aussi
consigner un accord externe avec contact client et référence justificative.
L’accord est une trace métier, sans revendication de signature qualifiée.
La confirmation de contenu par la coordination exige cet accord. Une réalisation
portant une variante ne se confirme pas avant son contenu approuvé.

Toute correction crée une version suivante liée à la précédente et exige un nouvel
accord. La version précédemment confirmée reste applicable jusqu’à confirmation
de la suivante. Auteurs, dates, accords et fichiers des anciennes versions restent
conservés ; le programme standard et son PDF ne sont pas réécrits.

## Contrôles serveur

Les nouveaux modèles ont des ACL de coordination et des règles globales par société.
Le portail n’a aucun droit ORM générique sur ces modèles, sur CRM, sur les lots ou
sur les inscriptions. Les contrôleurs authentifiés projettent des valeurs simples.
L’élévation lit d’abord l’habilitation du compte actif, puis vérifie lot, entité et
société avant chaque projection, nomination, téléchargement ou accord.

Les PDF client sont des champs binaires privés Odoo ; seuls les téléchargements
par dossier habilité les servent au portail, sans cache. Un jeton natif n’élargit
pas ce droit. Les PDF diffusés sont figés, même après retrait. La révocation retire
les projections et téléchargements ; elle ne peut retirer une copie déjà téléchargée.
Les modèles, rapports et contrôles participant existants restent indépendants.

La conservation suit l’[instruction humaine S11](s11-security-audit.md#conservation-et-instruction-humaine) : les catégories « habilitations », « nominations » et « dossiers client » doivent recevoir finalité, responsable et durées approuvées avant collecte réelle dans L01. Les versions, accords et PDF diffusés ne sont pas purgés automatiquement ; toute suppression requiert l’instruction du responsable et la vérification des gels. Aucune durée légale n’est inventée par cet incrément.

## Recette courte

1. Créer deux clients avec lots distincts, éventuellement sur une même session
   standard ; habiliter expressément un compte portail pour le lot A. Vérifier
   l’auteur/date, les seuls participants A et les demandes CRM qualifiées A.
2. Proposer deux fois un participant : une proposition, aucune inscription ni
   accès immédiat. Traiter manuellement la proposition et rattacher l’inscription
   du bon lot ; une inscription d’un autre lot est refusée.
3. Diffuser un PDF autorisé A. Tester B, un compte non habilité, les URL directes,
   les jetons et l’export ORM : aucun accès au document ou aux données privées.
   Révoquer A et retester les téléchargements et demandes.
4. Créer une variante client sur une réalisation intra. Soumettre, enregistrer
   l’accord client, confirmer le contenu puis la réalisation. Vérifier version,
   programme source, auteur et dates. Confirmation sans accord : refus.
5. Créer une version suivante : l’ancienne reste intacte et applicable ; le nouveau
   contenu exige son propre accord. Tester l’autre client et le lecteur catalogue :
   aucun accès au dossier confidentiel. Comparer le PDF standard avant/après.
6. Installer sur base vierge, puis mettre à jour depuis le main de départ et répéter
   la mise à jour : historiques et fichiers identiques, sans publication publique
   ni habilitation implicite. Le parcours CI `p01p06` conserve ces preuves et teste
   des soumissions/nominations concurrentes sur deux connexions réelles.
