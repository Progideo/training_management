# Consignes du dépôt Training Management

Ces consignes s’appliquent à l’ensemble du dépôt `Progideo/training_management`.
Elles reprennent les instructions du projet « NeoPro - odoo 20 », sans le
préambule propre au miroir local ChatGPT.

Lire d’abord l’[index documentaire](docs/README.md), puis les références utiles
à la tâche. La [spécification fonctionnelle v2](docs/references/Training_Management_Specification_Fonctionnelle_v2.md)
définit le périmètre ; le [prompt maître](docs/references/MASTER_PROMPT_TRAINING_MANAGEMENT_MODULE.md)
définit la méthode. Respecter la licence existante `LGPL-3.0-only`.

Tu interviens sur le projet « NeoPro - odoo 20 », consacré au développement de l’application native Odoo **Training Management**.

## Objectif et identité

- Cible : Odoo 20 Community sur serveur dédié OVH.
- Dépôt : `Progideo/training_management`.
- Module principal : `training_management`.
- Nom affiché : Training Management.
- Menu principal : Formations.
- Le module est générique et indépendant de NeoPro Academy, premier organisme utilisateur.
- Communiquer en français ; utiliser des identifiants techniques cohérents en anglais et des libellés traduisibles.

## Sources et décisions

Lire les instructions du dépôt, notamment `AGENTS.md`, ainsi que les spécifications et décisions pertinentes avant d’agir.

La spécification fonctionnelle v2 et ses évolutions validées définissent le périmètre. Le prompt maître de développement définit la méthode. Les décisions explicites les plus récentes de l’utilisateur prévalent sur les documents antérieurs.

Le fichier `MASTER_PROMPT_AUDIT_ODOO_19_NEOPRO_ACADEMY.md` est une référence historique : l’audit est suspendu et ses consignes ne doivent pas être réactivées automatiquement.

Ne pas supposer que les fichiers joints et le dépôt sont synchronisés. Signaler les divergences importantes et identifier la version de référence avant de les corriger.

## Périmètre validé

- Phase 1 : socle MVP et P01 à P08.
- Phase 2 : P09 à P16.
- P17 à P20 : après validation complémentaire explicite.

Préserver les exigences suivantes :
- Marché francophone mondial ; intraentreprise prioritaire, puis inscriptions individuelles.
- Présentiel, distanciel, mixte et eLearning.
- Commercialisation en MAD ou EUR ; virement bancaire, sans paiement en ligne au lancement.
- Supports principalement PDF, quiz et examens blancs.
- Examens blancs à questions choisies par le créateur, durée contrôlée, score et correction finale, tentatives illimitées.
- Émargement électronique dès le lancement ; papier possible selon les cas.
- Reprise Odoo 19 indispensable, avec migration manuelle contrôlée possible.
- Bonnes pratiques qualité compatibles avec l’objectif Qualiopi, sans revendiquer une certification effective.

## Intégration native Odoo

Privilégier dans cet ordre : standard Community, configuration, héritage ciblé, module communautaire compatible, développement spécifique justifié.

Vérifier la disponibilité et le comportement des fonctions dans le code exact d’Odoo 20 Community utilisé. Ne pas extrapoler une compatibilité depuis une documentation ancienne ou une fonctionnalité Enterprise.

Respecter les conventions officielles Odoo : structure des addons, manifest, ORM, modèles, vues héritées, sécurité, contrôleurs, QWeb, composants frontend, traductions, rapports et tests.

Ne pas modifier le cœur d’Odoo ni copier ses modules standards. Éviter les monkey patches et les dépendances inutiles.

Réutiliser les référentiels et workflows standards adaptés : contacts, utilisateurs, produits, ventes, factures, devises, pièces jointes, messages et activités. Ne pas créer de seconde authentification ou de référentiels concurrents.

Utiliser les interfaces natives Odoo. Toute application frontend séparée ou service supplémentaire doit être justifié et validé.

Étudier Surveys/Certification pour les examens blancs et démontrer sa couverture réelle des exigences avant de le retenir.

Séparer le métier générique, les intégrations, les adaptations NeoPro, les adaptations marocaines et les scripts de migration. Aucun nom d’entreprise, tarif, domaine ou compte bancaire codé en dur.

## Sécurité et qualité

Appliquer les autorisations côté serveur : groupes, droits d’accès, règles d’enregistrement et contrôles des méthodes et routes. Une vue ou un bouton masqué ne constitue pas une protection.

Distinguer société exploitante Odoo et entreprise cliente. Tester l’isolation entre sociétés, clients, groupes, sessions et participants.

Protéger les supports privés, pièces jointes, résultats, corrigés, exports, notifications et échanges. Limiter et justifier tout usage de `sudo()`.

Prévoir les répétitions, doubles soumissions et accès concurrents sur les opérations critiques. Le chronométrage des examens repose sur le serveur.

Le dépôt est public : aucun secret, donnée personnelle réelle, export client ou sauvegarde de production. Utiliser des données fictives pour les tests.

Respecter les licences des dépendances et la licence du dépôt.

## Développement et validation

Travailler par incréments fonctionnels cohérents, avec branches dédiées et pull requests lisibles.

Pour chaque incrément :
- Relier les changements aux exigences ou issues concernées.
- Réaliser des tests proportionnés au risque avec les outils compatibles Odoo.
- Vérifier les permissions avec des profils restreints.
- Vérifier les intégrations standards affectées.
- Fournir une procédure de recette courte.
- Indiquer les tests réellement exécutés et leurs résultats.

La simplicité d’usage et l’ergonomie font partie de la recette : un parcours fréquent doit rester court pour la personne qui l’exécute. Un garde-fou doit protéger une exigence identifiée ; sans exigence, ne pas l’ajouter.

Vérifier régulièrement l’installation sur base vierge et la mise à jour sur base existante. Préserver les historiques et prévoir les migrations nécessaires.

Ne jamais présenter une hypothèse comme une capacité démontrée, un test non exécuté comme réussi ou une fonctionnalité simulée comme opérationnelle.

## GitHub et documentation

GitHub est la référence pour le code, les issues, les pull requests, les décisions techniques et les preuves de tests.

Éviter les duplications : les issues portent le besoin, les pull requests expliquent les changements et leur validation, la documentation conserve les décisions durables.

Ne pas créer de suivi parallèle dans Jira ou Confluence sans demande explicite.

Rester simple et concis dans la documentation : une page par incrément (décisions, règles, recette courte), des phrases courtes, aucune répétition d’un document à l’autre (renvoyer par un lien), ni historique d’autorisations ni résultats d’exécution, qui restent dans les pull requests. Le même principe vaut pour les descriptions de PR et les réponses : résultat, validation réalisée, limite, prochaine action.

Maintenir les documents concernés lorsqu’une décision validée change le périmètre ou l’architecture. Ne pas modifier silencieusement une exigence validée pour faciliter l’implémentation.

## Autonomie et autorisations

Avancer de manière autonome sur les analyses, développements et tests déjà autorisés. Ne pas demander plusieurs fois la même autorisation.

Préparer un résultat concret et vérifiable avant de demander un arbitrage. Réserver les questions aux décisions qui affectent réellement le périmètre, l’architecture, les coûts, la sécurité ou les données.

Respecter les validations du dépôt. La validation des spécifications ne vaut pas autorisation de fusion, de déploiement ou de bascule de production.

Ne pas fusionner, déployer, modifier la production ou lancer une migration réelle sans autorisation explicite applicable.

Pour une opération OVH exécutée par l’utilisateur : donner une étape à la fois et attendre le résultat. Préserver les autres applications du serveur.

## Communication et continuité

Répondre de manière concise : résultat, validation réalisée, limite éventuelle, prochaine action.

Lire uniquement les fichiers et extraits utiles. Éviter les recherches répétées, les sorties volumineuses et les tests redondants sans risque concret à vérifier.

Pour une tâche complexe, établir un plan court et le tenir à jour. Si une nouvelle conversation devient préférable, fournir un prompt de reprise indiquant les références utiles, les décisions, l’état réel et la prochaine action.

Signaler lorsqu’un changement de modèle serait pertinent, sans prétendre l’effectuer automatiquement.
