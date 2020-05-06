"""Components of the BDI loop."""
from copy import deepcopy
from typing import Callable, List, Tuple

from .actions import StateConcurrent, StateInit
from .strategy import BestFirstSearch
from .heuristics import EasyRule, WeightedRule
from .memory import MAX_USAGE, get_usage
from .utils import STATUS, IncorrectTask, ResourceLimit, println


class Message:
    """Simple class to encode a message."""

    def __init__(
        self,
        object_problem: str,
        color: str,
        requester: str,
        status: STATUS,
        time: int = None,
    ):
        """Fill message fields.

        Parameters
        ----------
        object_problem: str
            name of the object concerning the problem
        color: str
            color of the box concerning the problem
        requester: str:
            name of agent that sends the sos message
        status: STATUS
            * STATUS.ok if agent solved the problem for another agent (response)
            * STATUS.fail if agent needs help (query)
        time: List[(int, (row, col))]
            time when the agent solves the problem at

        """
        self.object_problem = object_problem
        self.color = color
        self.requester = requester
        self.status = status
        self.time = time
        if status == STATUS.ok and time is None:
            raise IncorrectTask("Solutions to SOS messages require a time!")


class Agent:
    """Implement the belief and backtrack cost.

    Attributes
    ----------
    task: StateInit
        subproblem assigned by the manager
    strategy: BestFirstSearch
        child strategy of BestFirstSearch
    heuristic: Callable
        function to generate the heuristic. Default: calcHuristicsFor
    color: str
    name: str
    init_pos: tuple[x,y]
        initial position of the agent in the original subproblem
    status: STATUS
        * STATUS.ok if agent solved the problem
        * STATUS.fail if Frontier empty
        * STATUS.init if agent hasn't invoked self.solve()
    helping: Message
        Message if the agent has been assigned a request from other agent,
        `False` otherwise
    saved_solution: List
        solution as a path of actions. Used to avoid recomputing solutions when
        not required. `None` if the solution has not been found.

    """

    def __init__(
        self, task: StateInit, strategy: BestFirstSearch, heuristic: Callable = None,
    ):
        """Initialize the agent wit a task."""
        self.task = task
        self.init_task = deepcopy(task)
        self.strategy = strategy
        self.heuristic = heuristic if heuristic else EasyRule()
        self.color = list(task.goals.values())[0][0][1]
        self.name = list(task.agents.keys())[0]
        self.init_pos = list(task.agents.values())[0][0][0]
        # status can be ok, fail or init
        self.status = STATUS.init
        self.helping = False
        self.saved_solution = None

    def solve(self, inbox: List[Message]) -> Tuple[List, Message]:
        """Solve the tasks by search and communicate.

        Returns
        -------
        path: List
            path to goal
        message: Message
            Message of current state

        """
        # update beliefs and desires
        if self.status == STATUS.ok and not self.helping:
            # avoid recomputing solutions when not needed
            return self.saved_solution, self.broadcast()
        if inbox and self.status == STATUS.fail:
            to_del = False
            for i, message in enumerate(inbox):
                if message.requester == self.name:
                    self.consume_message(message)
                    to_del = i
                    break
            if to_del:
                del inbox[message]
        # execute intention
        searcher = self.strategy(self.task, self.heuristic)
        println(
            f"goals -> {self.task.goals}\n"
            f"agents -> {self.task.agents}\nboxes -> {self.task.boxes}\n\n"
        )
        println(self.task)
        path = self.search(searcher)
        println(path)
        # communicate
        self.status = STATUS.fail if path is None else STATUS.ok
        self.saved_solution = path
        return path, self.broadcast()

    def add_task(self, task: StateInit):
        """Merge task with previous task."""
        color = list(task.goals.values())[0][0][1]
        if color != self.color:
            IncorrectTask(f"Agent {self.name}: I'm {self.color}, not {color}.")
        self.task.goals = {**self.task.goals, **task.goals}

    def marginal_task_cost(self, broadcasted_task: StateInit) -> float:
        """Compute cost of adding task `broadcasted_task`.

        Used in the top-down assignment by the manager when there is more than
        one agent with the same color. This should force the agents to be used
        even if one of the agents is very close to all the boxes.

        Without using times it may not be so good at distributing...
        """
        # the broadcasted task is guaranteed to have only one goal
        pos, color = list(broadcasted_task.goals.values())[0][0]
        goal_key = list(broadcasted_task.goals.keys())[0][0]
        c_union = float("inf")
        if color != self.color:
            return c_union
        self.heuristic(broadcasted_task)
        c_ts = broadcasted_task.f
        joint_task = deepcopy(self.task)
        joint_task.addGoal(goal_key, pos, color)
        cost = self.heuristic(joint_task)
        if cost is None:
            cost = c_union
        c_union = min(c_union, cost)
        return c_union - c_ts

    def consume_message(self, message: Message) -> StateInit:
        """Take a message."""
        if self.status == STATUS.fail:
            curr_pos = message.time[0][1]
            concurrent = {}
            for event in message.time:
                pos = event[1]
                if curr_pos[0] != pos[0] or curr_pos[1] != pos[1]:
                    curr_pos = pos
                    concurrent[event[0]] = {message.object_problem: pos}
            self.task = StateConcurrent(self.task, concurrent)
            # println(self.task.__dict__)
            # import sys; sys.exit(0)
            self.task.t = 0
        else:
            println(f"Agent {self.name} received message!")
            self.helping = message
            self.task = deepcopy(self.init_task)
            self.heuristic = WeightedRule(message.object_problem)
            # solution will be recomputed with updated priorities in heuristics
        # TODO: logic of weighting the goal here!

    def broadcast(self) -> Message:
        """Send a `Message` of stuff the agent wants to communicate."""
        message = False
        if self.status == STATUS.fail:
            message = self._sos()
            self.task.forget_exploration()
        if self.helping:
            message = self._send_success()
        return message

    def _sos(self) -> StateInit:
        """Identify problem and formulate solution."""
        box, color = self._identify_problem()
        return Message(
            object_problem=box,
            color=color,
            requester=self.name,
            status=self.status,
            time=None,
        )

    def _send_success(self) -> StateInit:
        """Return a message indicating that the problem was solved."""
        # TODO: weight heuristics and recompute alternative solution
        time_pos = self.task.bestPath(format=self.helping.object_problem)
        message = Message(
            self.helping.object_problem,
            self.helping.color,
            self.helping.requester,
            self.status,
            time_pos,
        )
        self.helping = False
        return message

    def track_back(self, looking_for: str = "") -> List:
        """Trace the object `looking_for` position in every explored nodes."""
        if not looking_for:
            looking_for = self.name
        explored = self.task.explored
        # set -> list -> dict (key -> list -> (pos, color))
        trace = []
        for minrep in explored:
            exp = eval(minrep)
            for object_dict in exp:
                key = list(object_dict)[0]
                if key == self.name:
                    trace.append(object_dict[key][0][0])
        return trace

    def _identify_problem(self) -> str:
        """Identify why frontier is empty.

        Returns
        -------
        blocking: List[str]
            goal and color as strings of the block which is blocking the agent

        """
        boxes = {
            box: pos_color[0]
            for box, pos_color in self.task.boxes.items()
            if pos_color[0][1] != self.color
        }
        agent_trace = self.track_back(self.name)
        println(agent_trace)
        for box, pos_color in boxes.items():
            for agent_pos in agent_trace:
                if self.task.Neighbour(pos_color[0], agent_pos):
                    return box, pos_color[1]

    def search(self, strategy: BestFirstSearch) -> List:
        """Search function.

        Returns
        -------
        Path to the solutions (in actions) or None.

        """
        iterations = 0
        if strategy.leaf.isGoalState():
            println(f"Agent {self.name}: state is Goal state (0 nodes explored)!")
            return []

        while not strategy.leaf.isGoalState():
            if iterations == 1000:
                println(f"{strategy.count} nodes explored")
                iterations = 0

            if get_usage() > MAX_USAGE:
                raise ResourceLimit("Maximum memory usage exceeded.")
                return None

            strategy.explore_and_add()

            if strategy.frontier_empty():
                println(f"Frontier empty! ({strategy.count} nodes explored)")
                return None

            strategy.get_and_remove_leaf()

            if strategy.leaf.isGoalState():
                println(
                    f"(Subproblem) Solution found with "
                    f"{len(strategy.leaf.explored)} nodes explored"
                )
                self.task = strategy.leaf
                return strategy.walk_best_path()

            iterations += 1
