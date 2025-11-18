class Sensors:
    def __init__(self, espece):
        self.espece = espece

    def detecter(self, world_objects):
        self_detection = self.espece.sens.get("detection", 0)
        detection_range = self_detection 
        objets_detectes = [obj for obj in world_objects if obj.distance < detection_range]
        return objets_detectes
    def detecter_visuellement(self, world_objects):
        self_detection_visuelle = self.espece.sens.get("detection_visuelle", 0)
        detection_range = self_detection_visuelle 
        objets_detectes = [obj for obj in world_objects if obj.distance < detection_range]
        return objets_detectes
