import random
from introcs import Vector2
from dataclasses import dataclass
import math

numberofPalinaPoints = 5
numberofPredators = 1
sizeX = 5
sizeY = 5

@dataclass
class Palina_Point:
    id: str
    x0: float
    x1: float
    v0: float
    v1: float

    @property
    def relative_velocity(self) -> Vector2:
        return Vector2(self.v0 / sizeX, self.v1 / sizeY)
    
@dataclass
class Json_Decompressor:
    step: int
    fish: dict
    actors: dict




class ParticleSimulator(object):
    def __init__(self):
        self.fish = self.initialize_dictionary(numberofPalinaPoints)
        self.actors = self.initialize_dictionary(numberofPredators)
        self.loopCounter = -1

    def initialize_dictionary(self, limit: int) -> dict:
        tempDict = {}
        for i in range(limit):
            pos = Vector2(0.5 * sizeX, 0.5 * sizeY)
            orient = Vector2(random.uniform(0, 1), random.uniform(0, 1)).normalize()
            newPoint = Palina_Point(i, pos.x, pos.y, orient.x, orient.y)
            tempDict[i] = newPoint
        
        return tempDict

    def update(self) -> Json_Decompressor:
        # Generate the next step
        self.loopCounter += 1

        temp_dict = {}
        for i in range(numberofPalinaPoints):
            temp_dict[i] = self.perturb_point(self.fish[i])

        self.fish = temp_dict
        
        temp_dict = {}
        for i in range(numberofPredators):
            temp_dict[i] = self.perturb_point(self.actors[i])
        
        self.actors = temp_dict

        return Json_Decompressor(self.loopCounter, self.fish, self.actors)

    def perturb_point(self, current_point: Palina_Point) -> Palina_Point:
        # Continue moving in the current direction unless we hit a wall
        step = current_point.relative_velocity
        step = (step.normalize().rotate(0.01) / 150).__mul__(Vector2(sizeX, sizeY))

        if (current_point.x0 + step.x > 0.9 * sizeX or 
            current_point.x0 + step.x < 0.1 * sizeX):
            step.x = -step.x

        if (current_point.x1 + step.y > 0.9 * sizeY or
            current_point.x1 + step.y < 0.1 * sizeY):
            step.y = -step.y

        stepped_vector = Vector2(current_point.x0 + step.x, current_point.x1 + step.y)
        stepped_orient = step.__truediv__(Vector2(sizeX, sizeY)) * 150

        if (math.isnan(stepped_vector.x) or math.isnan(stepped_vector.y)):
            print("Overstepped vector")

        return Palina_Point(current_point.id, stepped_vector.x, stepped_vector.y, stepped_orient.x, stepped_orient.y)
    