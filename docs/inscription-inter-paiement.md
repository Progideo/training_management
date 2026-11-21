# Inscription inter-entreprises avec paiement

Décisions du 21 novembre 2026. Elles s'appliquent à une session inter publiée dont la
formation a un tarif inter public (produit « par personne »). Sans tarif public, la
[demande d'inscription CRM](p16-session-status-alerts.md) reste le parcours.

## Règles

- **Compte** : il faut être connecté, puisque la commande, son paiement et le portail participant sont personnels. Un visiteur est renvoyé vers la connexion ou l'inscription.
- **Places** : de 1 à 5 participants, dans la limite des places restantes. Une seule inscription en cours par acheteur et par session.
- **Commande** :
  - l'inscription crée une commande native au nom de l'acheteur, sans étape de devis pour le visiteur ;
  - l'acheteur est le seul contact habilité ;
  - les places sont réservées sur la ligne de commande.
- **Session confirmée** : l'acheteur paie aussitôt sur la page de la commande du portail Odoo.
- **Session non confirmée** :
  - l'inscription est enregistrée sans paiement et un courriel invite à attendre ;
  - le paiement est refusé côté serveur, y compris par appel direct à la route de transaction ;
  - à la confirmation de la session, chaque inscription impayée reçoit une seule demande de paiement.
- **Libération** :
  - une place impayée est conservée jusqu'à 7 jours avant le début de la session, puis libérée ;
  - après cette date, le paiement est refusé ;
  - en deçà de 7 jours, seule une session confirmée accepte une inscription, payée aussitôt.
- **Paiement** : il confirme la commande et les places. L'accès pédagogique reste une décision explicite de la coordination ([S03](s03-enrollment-access.md)).
- **Devis** : le lien « Besoin d'un devis pour votre entreprise ? » mène toujours à la demande de devis.
- **Prestataires et moyens de paiement** : ils restent ceux configurés dans Odoo (#102).

## Recette courte

1. Session publiée et non confirmée, avec tarif :
   - un visiteur est renvoyé vers la connexion ;
   - une fois connecté, il s'inscrit pour 2 participants : commande en brouillon, places réservées, courriel d'attente ;
   - aucun paiement n'est possible.
2. Confirmer la session : la commande passe à « envoyée » et une seule demande de paiement part. Payer : commande et places confirmées, aucune inscription nominative créée.
3. Session confirmée : l'inscription mène directement au paiement. Un collègue non habilité ne voit pas la commande.
4. Inscription impayée : 7 jours avant le début, la place revient à la session et le paiement est refusé.
