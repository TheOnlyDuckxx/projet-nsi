# Keystone : The Long Evolution

> Un jeu de simulation évolutive où chaque choix forge le destin d'une espèce.

---

## Présentation générale

**Keystone : The Long Evolution** est un jeu de simulation développé en Python avec la bibliothèque Pygame, dans le cadre du projet NSI.

Le joueur y incarne non pas un individu, mais une **espèce entière** plongée dans un monde naturel hostile et en constante évolution. Depuis les premières heures de survie dans la nature sauvage jusqu'à l'émergence d'une proto-civilisation, chaque décision influence durablement le développement biologique et social de l'espèce.

---

## Concept et univers

L'idée centrale du jeu est simple : **la nature ne pardonne pas, mais elle récompense l'adaptation.**

Le joueur commence avec une poignée d'individus aux capacités limitées, dans un monde généré aléatoirement. Chaque être possède ses propres statistiques (physiques, sensorielles, mentales, sociales), son comportement autonome et ses besoins vitaux. Sans intervention, ils survivent — ou meurent.

Au fil du temps, l'espèce accumule de l'expérience collective. Des **mutations** deviennent disponibles, permettant d'orienter l'évolution biologique : meilleure résistance, sens aiguisés, capacités cognitives accrues… Chaque choix ferme d'autres portes. L'évolution est irréversible.

Progressivement, des **classes sociales** émergent au sein de la population (savants, croyants, belligérants, pacifistes), reflétant la direction donnée par le joueur à sa société en gestation. Des **technologies** se débloquent, des **structures** se construisent, et une véritable civilisation commence à prendre forme — fragile, façonnée par son histoire.

---

## Fonctionnalités principales

### Un monde vivant et procédural
Le monde est généré de manière procédurale à chaque nouvelle partie, garantissant une expérience unique. Un cycle jour/nuit dynamique et un système météorologique influencent les comportements des individus et les ressources disponibles.

### Des individus autonomes
Chaque membre de l'espèce est une entité indépendante dotée d'une IA comportementale : récolte, chasse, défense, reproduction. Ils agissent, réagissent, et meurent selon les conditions du monde et leurs capacités propres.

### Le système de mutations
Au fil de la progression, le joueur se voit proposer des **mutations permanentes** qui modifient en profondeur les statistiques et capacités de l'espèce. Ces choix sont stratégiques et définitifs — ils orientent l'évolution biologique de manière irréversible.

### Événements et crises
Le monde génère des **événements dynamiques** qui mettent l'espèce à l'épreuve : hordes ennemies, catastrophes naturelles, opportunités rares. Ces crises forcent le joueur à s'adapter et créent des histoires uniques à chaque partie.

### Progression technologique et sociale
Un arbre de technologies, un système de crafts et de construction, ainsi qu'un système de **quêtes** guident la progression sur le long terme. La classe principale de l'espèce — choisie lors d'un événement clé — oriente les quêtes disponibles et les bonus obtenus.

### Historique du monde
Chaque partie génère un **historique persistant** des événements majeurs vécus par l'espèce, formant une mémoire narrative unique à chaque run.

---

## Boucle de jeu

```
Créer l'espèce  →  Survivre dans la nature  →  Récolter & Construire
       ↑                                                ↓
 Gérer les crises                       Débloquer mutations & technologies
       ↑                                                ↓
 Événements mondiaux  ←─────────  Développer la civilisation
```

1. **Création** — Le joueur nomme son espèce, choisit sa couleur et ses paramètres de départ.
2. **Survie** — Assurer les besoins vitaux des premiers individus dans un environnement hostile.
3. **Développement** — Récolter des ressources, construire les premières structures.
4. **Évolution** — Choisir les mutations et technologies qui définissent l'identité de l'espèce.
5. **Civilisation** — Orienter la société vers une spécialisation (scientifique, guerrière, spirituelle…).
6. **Crises** — Faire face aux événements du monde et adapter sa stratégie.

---

