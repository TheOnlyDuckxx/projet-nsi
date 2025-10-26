class Sensors:
    def __init__(self, espece):
        self.espece = espece

    def detecter(self, world_objects):
        vue = self.espece.sens.get("vision", 0)
        ouie = self.espece.sens.get("ouie", 0)
        odorat = self.espece.sens.get("odorat", 0)

        detection_range = vue * 10 + ouie * 5 + odorat * 2
        objets_detectes = [obj for obj in world_objects if obj.distance < detection_range]

        return objets_detectes