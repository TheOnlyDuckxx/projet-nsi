class _RowProxy:
    def __init__(self, fog, y: int, kind: str):
        self.fog = fog
        self.y = y
        self.kind = kind

    def __getitem__(self, x: int) -> bool:
        if self.kind == "visible":
            return self.fog.is_visible(x, self.y)
        return self.fog.is_explored(x, self.y)


class _GridProxy:
    def __init__(self, fog, kind: str):
        self.fog = fog
        self.kind = kind

    def __getitem__(self, y: int):
        return _RowProxy(self.fog, y, self.kind)


class FogOfWar:
    """
    Fog scalable :
    - visible : set de tuiles visibles (reset chaque recompute)
    - explored : bitset par chunk (persistant, progressif tuile par tuile)
    """
    def __init__(self, width: int, height: int, chunk_size: int = 32, wrap_x: bool = False):
        self.width = int(width)
        self.height = int(height)
        self.chunk_size = int(chunk_size)
        self.wrap_x = bool(wrap_x)

        self._visible = set()          # {(x,y), ...}
        self._explored_chunks = {}     # (cx,cy) -> bytearray bitset

        # compat iso_render : fog.visible[y][x] et fog.explored[y][x]
        self.visible = _GridProxy(self, "visible")
        self.explored = _GridProxy(self, "explored")

    def clear_visible(self):
        self._visible.clear()

    def _norm_x(self, x: int) -> int:
        if self.wrap_x:
            return x % self.width
        return x

    def _chunk_key(self, x: int, y: int):
        cs = self.chunk_size
        cx = x // cs
        cy = y // cs
        lx = x - cx * cs
        ly = y - cy * cs
        return (cx, cy), (lx + ly * cs)

    def _get_bitset(self, cx: int, cy: int, create: bool) -> bytearray | None:
        key = (cx, cy)
        b = self._explored_chunks.get(key)
        if b is None and create:
            size_bits = self.chunk_size * self.chunk_size
            b = bytearray((size_bits + 7) // 8)
            self._explored_chunks[key] = b
        return b

    def _set_explored(self, x: int, y: int):
        (cx, cy), idx = self._chunk_key(x, y)
        b = self._get_bitset(cx, cy, create=True)
        bi = idx >> 3
        bm = 1 << (idx & 7)
        b[bi] |= bm

    def is_explored(self, x: int, y: int) -> bool:
        if not (0 <= y < self.height):
            return False
        x = self._norm_x(x)
        if not (0 <= x < self.width):
            return False

        (cx, cy), idx = self._chunk_key(x, y)
        b = self._get_bitset(cx, cy, create=False)
        if b is None:
            return False
        bi = idx >> 3
        bm = 1 << (idx & 7)
        return (b[bi] & bm) != 0

    def is_visible(self, x: int, y: int) -> bool:
        if not (0 <= y < self.height):
            return False
        x = self._norm_x(x)
        return (x, y) in self._visible

    def recompute(self, observers, get_radius, light_level: float):
        self.clear_visible()

        light = max(0.0, min(1.0, float(light_level)))

        for ent in observers:
            cx, cy = int(ent.x), int(ent.y)
            if not (0 <= cy < self.height):
                continue
            cx = self._norm_x(cx)
            if not (0 <= cx < self.width):
                continue

            base_radius = int(get_radius(ent))
            r = max(1, int(round(base_radius * (1.0 + light))))
            r2 = r * r

            y0 = max(0, cy - r)
            y1 = min(self.height - 1, cy + r)

            for y in range(y0, y1 + 1):
                dy = y - cy
                dy2 = dy * dy
                x0 = cx - r
                x1 = cx + r

                for x in range(x0, x1 + 1):
                    dx = x - cx
                    if dx * dx + dy2 > r2:
                        continue

                    xx = self._norm_x(x)
                    if not (0 <= xx < self.width):
                        continue

                    self._visible.add((xx, y))
                    self._set_explored(xx, y)
