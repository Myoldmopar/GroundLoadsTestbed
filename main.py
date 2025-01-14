from pathlib import Path
from random import random
from scp.water import Water


repo_root = Path(__file__).resolve().parent
output_folder = repo_root / 'outputs'
output_folder.mkdir(exist_ok=True)


class HeatPump:
    def __init__(self) -> None:
        self.current_loop_demand = 0
        with (repo_root / 'building_loads.csv').open() as f:
            lines = f.read().strip().split('\n')
            self.building_loads = [-float(x.strip()) for x in lines]
    
    def simulate(self, loop) -> None:
        building_load = self.building_loads[loop.hour_index]
        if building_load > 0:
            # rejection from the heat pump onto the loop, so the outlet temp increases
            self.current_loop_demand = building_load * (1.09244 + 0.000314 * loop.heat_pump_inlet_temp + 0.000114 * loop.heat_pump_inlet_temp**2)
        else:
            # absorbing heat from the loop, so the outlet temp will decrease
            self.current_loop_demand = building_load * (0.705459 + 0.005447 * loop.heat_pump_inlet_temp + -0.000077 * loop.heat_pump_inlet_temp**2)
        loop.glhe_inlet_temp = loop.heat_pump_inlet_temp + self.current_loop_demand / (loop.mass_flow_rate * loop.cp)


class GLHE:
    def __init__(self, use_effectiveness) -> None:
        self.ground_loads_for_sizing = []
        self.ground_temperature = 12
        self.effectiveness = 0.7
        self.use_effectiveness = use_effectiveness

    def simulate(self, loop) -> None:
        if self.use_effectiveness:
            max_delta_t = loop.heat_pump_inlet_temp - self.ground_temperature
            actual_delta_t = self.effectiveness * max_delta_t
            simulated_heat_transfer = actual_delta_t * loop.mass_flow_rate * loop.cp
        else:
            simulated_heat_transfer = loop.hp.current_loop_demand
        self.ground_loads_for_sizing.append(simulated_heat_transfer)
        loop.heat_pump_inlet_temp = loop.glhe_inlet_temp - simulated_heat_transfer / (loop.mass_flow_rate * loop.cp)


class Loop:
    def __init__(self, initial_loop_temp: float, glhe_effectiveness: bool) -> None:
        self.heat_pump_inlet_temp = initial_loop_temp
        self.heat_pump_inlet_temp_history = []
        self.glhe_inlet_temp = initial_loop_temp
        self.glhe_inlet_temp_history = []
        self.cp = Water().specific_heat(initial_loop_temp)
        self.hp = HeatPump()
        peak_building_load = max([abs(x) for x in self.hp.building_loads])
        nice_delta_t = 20
        self.mass_flow_rate = peak_building_load / (self.cp * nice_delta_t)
        self.glhe = GLHE(use_effectiveness=glhe_effectiveness)
        self.hour_index = -1
    
    def simulate(self):
        for day in range(365):
            for hour in range(24):
                self.hour_index += 1
                self.hp.simulate(self)
                self.glhe.simulate(self)
                self.heat_pump_inlet_temp_history.append(self.heat_pump_inlet_temp)
                self.glhe_inlet_temp_history.append(self.glhe_inlet_temp)
                # print(f"{self.heat_pump_inlet_temp=}; {self.glhe_inlet_temp=}")


if __name__ == "__main__":
    l = Loop(25.5, False)
    l.simulate()
    ground_loads_no_effectiveness = l.glhe.ground_loads_for_sizing
    hp_eft_no = l.heat_pump_inlet_temp_history
    ghe_eft_no = l.glhe_inlet_temp_history
    l = Loop(25.5, True)
    l.simulate()
    ground_loads_with_effectiveness = l.glhe.ground_loads_for_sizing
    hp_eft_yes = l.heat_pump_inlet_temp_history
    ghe_eft_yes = l.glhe_inlet_temp_history
    with (output_folder / 'outputs.csv').open('w') as f:
        f.write(f"Index,Q_ground_no,Q_ground_yes,HP_EFT_no,HP_EFT_yes,GHE_EFT_no,GHE_EFT_yes\n")
        ind = 0
        for args in zip(ground_loads_no_effectiveness, ground_loads_with_effectiveness, hp_eft_no, hp_eft_yes, ghe_eft_no, ghe_eft_yes):
            ind += 1
            f.write(f"{ind},")
            for i, a in enumerate(args):
                if i < len(args) - 1:
                    f.write(f"{a},")
                else:
                    f.write(f"{a}")
            f.write("\n")
