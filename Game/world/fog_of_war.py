class FogOfWar:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        
        self.visible  = [[False for _ in range(width)] for _ in range(height)]
        self.explored = [[False for _ in range(width)] for _ in range(height)]

    def clear_visible(self):
        for y in range(self.height):
            for x in range(self.width):
                self.visible[y][x] = False

    def recompute(self, observers, get_radius):
        self.clear_visible()

        for ent in observers:
            cx, cy = int(ent.x), int(ent.y)
            if not (0 <= cx < self.width and 0 <= cy < self.height):
                continue

            r = get_radius(ent)
            r2 = r * r

            for y in range(max(0, cy-r), min(self.height, cy+r+1)):
                dy = y - cy
                dy2 = dy*dy
                row_vis = self.visible[y]
                row_exp = self.explored[y]

                for x in range(max(0, cx-r), min(self.width, cx+r+1)):
                    dx = x - cx
                    if dx*dx + dy2 <= r2:
                        row_vis[x] = True
                        row_exp[x] = True   # ← NEW : devenue explorée
