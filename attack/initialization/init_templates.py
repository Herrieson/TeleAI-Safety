import os
import json
import random

class InitTemplates:
    def __init__(self):
        pass
    
    def get_templates(self, name, num):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_dir, './init_templates.json')
        with open(file_path) as f:
            templates = json.load(f)
        all_templates = templates['attack'][name]
        
        if num == -1:
            return all_templates
        
        res = random.sample(all_templates, num)
        return res
    
class PopulationInitializer:
    def init_population(self, data_path):
        lower_path = str(data_path).lower()
        if lower_path.endswith(".json"):
            with open(data_path) as f:
                population = json.load(f)
            return population

        if lower_path.endswith(".jsonl"):
            population = []
            with open(data_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    population.append(json.loads(line))
            return population

        raise ValueError(f"Unsupported data file type for population: {data_path}")
