"""Client that receives messages from the server."""
import argparse
import re
import string
import sys
from typing import List

import numpy as np

from _io import TextIOWrapper
from multi_sokoban.actions import StateInit
from multi_sokoban.strategy import BestFirstSearch, aStarSearch, greedySearch
from multi_sokoban.manager import Manager
from multi_sokoban.utils import println
from heuristics import dGraph, EasyRule


class ParseError(Exception):
    """Define parsing error exception."""

    pass


class SearchClient:
    """Contain the AI, strategy and parsing."""

    def __init__(self, server_messages: TextIOWrapper, strategy: str):
        """Init object."""
        self.colors_re = re.compile(r"^([a-z]+):\s*([0-9])\s*")
        self.invalid_re = re.compile(r"[^A-Za-z0-9+]")
        self.colors = {}
        self.initial_state = self.parse_map(server_messages)
        self._strategy = None
        self.heuristic = dGraph(self.initial_state)
        self.add_strategy(strategy)
        sys.setrecursionlimit(1000000000)

    @property
    def strategy(self) -> BestFirstSearch:
        """Get strategy, the setter handles different types of inputs."""
        return self._strategy

    @strategy.setter
    def strategy(self, strategy: str):
        if isinstance(strategy, BestFirstSearch):
            self._strategy = strategy
        else:
            if strategy == "astar":
                self._strategy = aStarSearch
            elif strategy == "wastar":
                raise NotImplementedError
            elif strategy == "greedy":
                self._strategy = greedySearch

    def add_strategy(self, strategy: str):
        """Initialize strategy, just for the __init__ method."""
        self.strategy = strategy

    def parse_map(self, server_messages: TextIOWrapper) -> StateInit:
        """Parse the initial server message into a map."""
        # a level has a header with color specifications followed by the map
        # the map starts after the line "#initial"
        line = server_messages.readline().rstrip()
        initial = False  # mark start of level map
        goal = False  # mark start of level map
        map = []
        goal_state = []
        col_count = 0
        while line:
            if goal:
                if line.find("#end") != -1:
                    len_line = max(len(l) for l in map)
                    for i in range(len(map)):
                        map[i] += "+" * (len_line - len(map[i]))
                        goal_state[i] += "+" * (len_line - len(goal_state[i]))
                    println("\n".join(["".join(line) for line in map]))
                    return self.build_map(map, goal_state)
                goal_state.append(list(self._formatl(line)))
            elif initial:
                if line.find("#goal") != -1:
                    goal = True
                else:
                    map.append(list(self._formatl(line)))
            else:
                if line.find("#initial") != -1:
                    initial = True
                else:
                    color_matched = self.colors_re.search(line)
                    if color_matched:
                        col_count += 1
                        color = color_matched[1]
                        self.colors[color_matched[2]] = color
                        for obj in line[len(color) + 5 :].split(", "):
                            self.colors[obj] = color
            line = server_messages.readline().replace("\r", "")[:-1]  # chop last

    def _formatl(self, line: str):
        prev = len(line)
        new_line = re.sub(r'^.*?\+', '+', line)
        while len(new_line) < prev:
            new_line = "+" + new_line
        return new_line

    def build_map(self, map: List, goal_state: List) -> StateInit:
        """Build the StateInit from the parsed map.

        addMap just parses rigid positions (not agent and boxes), so
        get the positions of the agents and boxes and remove them from map
        """
        state = StateInit()
        all_objects = []
        agent_n_boxes = string.digits + string.ascii_uppercase
        possible_colors = set(self.colors.values())
        println(possible_colors)
        all_objects = self._locate_objects(np.array(map), agent_n_boxes)
        # it is required to add the map first and then the rest level objects
        state.addMap(map)
        for obj, pos, color in all_objects:
            row, col = pos
            if obj in string.digits:
                state.addAgent(obj, (row, col), color)
            elif obj in string.ascii_uppercase:
                if color in possible_colors:
                    state.addBox(obj, (row, col), color)
                else:
                    state.map[row, col] = "+"
        goals = string.ascii_uppercase
        all_objects = self._locate_objects(np.array(goal_state), goals)
        for obj, pos, color in all_objects:
            row, col = pos
            state.addGoal(obj, (row, col), color)
        println(state)
        return state

    def _locate_objects(self, map: np.array, possible_objects: str) -> List:
        all_objects = []
        # print(map, file=sys.stderr, flush=True)
        for obj in possible_objects:
            agent_pos = np.where(map == obj)
            if len(agent_pos) > 0:
                for x, y in zip(agent_pos[0], agent_pos[1]):
                    color = self.colors[obj] if obj in self.colors else None
                    all_objects.append([obj, (x, y), color])
                map[agent_pos] = " "
        return all_objects

    def search(self) -> List:
        """Apply search algorithm."""
        println(f"Starting search with strategy {self.strategy}.")
        boss = Manager(self.initial_state, self.strategy, self.heuristic)
        paths = boss.run()
        nodes_explored = boss.nodes_explored
        return paths, nodes_explored


def parse_arguments() -> argparse.ArgumentParser:
    """Parse CLI arguments, such as strategy and  nbn limit."""
    parser = argparse.ArgumentParser(
        description="Simple client based on state-space graph search."
    )
    parser.add_argument(
        "--max-memory",
        metavar="<MB>",
        type=float,
        default=2048.0,
        help="The maximum memory usage allowed in MB (soft limit).",
    )
    strategy_group = parser.add_mutually_exclusive_group()
    strategy_group.add_argument(
        "-astar",
        action="store_const",
        dest="strategy",
        const="astar",
        help="Use the A* strategy.",
    )
    strategy_group.add_argument(
        "-wastar",
        action="store_const",
        dest="strategy",
        const="wastar",
        help="Use the WA* strategy.",
    )
    strategy_group.add_argument(
        "-greedy",
        action="store_const",
        dest="strategy",
        const="greedy",
        help="Use the Greedy strategy.",
    )
    args = parser.parse_args()

    return args


def run_loop(strategy: str, memory: float):
    """Iterate over main loop Server->Client->Server."""
    global MAX_USAGE
    MAX_USAGE = memory
    server_messages = sys.stdin
    client = SearchClient(server_messages, strategy)
    solution, nodes_explored = client.search()
    if solution is None:
        println("Unable to solve level.")
        sys.exit(1)
    else:
        println("\nSummary for {}.".format(strategy))
        println(f"Total nodes explored: {nodes_explored}")
        println("Found solution of length {}.".format(len(solution)))
        println(f"Solution -> {solution}")
        for state in solution:
            print(state, flush=True)
            response = server_messages.readline().rstrip()
            if "false" in response:
                println(
                    f"Server responsed with '{response}' to the action"
                    f" '{state}' applied in:\n{solution}\n"
                )
                break


if __name__ == "__main__":
    args = parse_arguments()
    print("Karen\n", flush=True)
    run_loop(args.strategy, args.max_memory)
