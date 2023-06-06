# import random
# from introcs import Vector2
# from dataclasses import dataclass
# import math
# import rendersettings as rs


# @dataclass
# class Palina_Point:
#     id: str
#     x0: float
#     x1: float
#     v0: float
#     v1: float

#     @property
#     def relative_velocity(self) -> Vector2:
#         return Vector2(self.v0 / rs.sizeX, self.v1 / rs.sizeY)
    
# @dataclass
# class Json_Decompressor:
#     step: int
#     fish: dict
#     actors: dict




# class ParticleSimulator(object):
#     def __init__(self):
#         self.fish = self.initialize_dictionary(rs.numberofPalinaPoints)
#         self.actors = self.initialize_dictionary(rs.numberofPredators)
#         self.loopCounter = -1

#     def initialize_dictionary(self, count: int) -> dict:
#         """Initializes a dictionary of Palina_Points, with the starting position of each
#         point being in the middle of the arena. The Palina_Points are indexed by a monotonously
#         increasing sequence of integers starting at 0 and ending at count-1.

#         Args:
#             count (int): The number of dictionary entries to create

#         Returns:
#             dict: The assembled dictionary of type {int: Palina_Point}
#         """
#         tempDict = {}
#         for i in range(count):
#             # Situate in the middle of the arena
#             pos = Vector2(0.5 * rs.sizeX, 0.5 * rs.sizeY)
#             orient = Vector2(random.uniform(0, 1), random.uniform(0, 1)).normalize()
#             newPoint = Palina_Point(i, pos.x, pos.y, orient.x, orient.y)
#             tempDict[i] = newPoint
        
#         return tempDict

#     def update(self) -> Json_Decompressor:
#         """Advances the ParticleSimulator() self.fish and self.actors instance dictionaries forward by one step.

#         Returns:
#             Json_Decompressor: An instance of the dataclass that represents the new step
#         """
#         self.loopCounter += 1

#         temp_dict = {}
#         for i in range(rs.numberofPalinaPoints):
#             temp_dict[i] = self.perturb_point(self.fish[i])

#         self.fish = temp_dict
        
#         temp_dict = {}
#         for i in range(rs.numberofPredators):
#             temp_dict[i] = self.perturb_point(self.actors[i])
        
#         self.actors = temp_dict

#         return Json_Decompressor(self.loopCounter, self.fish, self.actors)

#     def perturb_point(self, current_point: Palina_Point) -> Palina_Point:
#         """Moves a Palina_Point one step further along its trajectory

#         Args:
#             current_point (Palina_Point): The Palina_Point to be stepped forward

#         Returns:
#             Palina_Point: The stepped Palina_Point
#         """
#         # Continue moving in the current direction unless we hit a wall
#         step = current_point.relative_velocity
#         step = (step.normalize().rotate(0.01) / 150).__mul__(Vector2(rs.sizeX, rs.sizeY))

#         if (current_point.x0 + step.x > 0.9 * rs.sizeX or 
#             current_point.x0 + step.x < 0.1 * rs.sizeX):
#             step.x = -step.x

#         if (current_point.x1 + step.y > 0.9 * rs.sizeY or
#             current_point.x1 + step.y < 0.1 * rs.sizeY):
#             step.y = -step.y

#         stepped_vector = Vector2(current_point.x0 + step.x, current_point.x1 + step.y)
#         stepped_orient = step.__truediv__(Vector2(rs.sizeX, rs.sizeY)) * 150

#         if (math.isnan(stepped_vector.x) or math.isnan(stepped_vector.y)):
#             print("Overstepped vector")

#         return Palina_Point(current_point.id, stepped_vector.x, stepped_vector.y, stepped_orient.x, stepped_orient.y)
    