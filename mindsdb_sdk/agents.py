from requests.exceptions import HTTPError
from typing import List, Union
import datetime

from mindsdb_sdk.models import Model
from mindsdb_sdk.skills import Skill, Skills
from mindsdb_sdk.utils.objects_collection import CollectionBase


class AgentCompletion:
    """Represents a full MindsDB agent completion"""
    def __init__(self, content: str):
        self.content = content

    def __repr__(self):
        return self.content


class Agent:
    """Represents a MindsDB agent"""
    def __init__(
            self,
            name: str,
            model_name: str,
            skills: List[Skill],
            params: dict,
            created_at: datetime.datetime,
            updated_at: datetime.datetime,
            collection: CollectionBase = None
            ):
        self.name = name
        self.model_name = model_name
        self.skills = skills
        self.params = params
        self.created_at = created_at
        self.updated_at = updated_at
        self.collection = collection

    def completion(self, messages: List[dict]) -> AgentCompletion:
        return self.collection.completion(self.name, messages)

    def __repr__(self):
        return f'{self.__class__.__name__}(name: {self.name})'

    def __eq__(self, other):
        if self.name != other.name:
            return False
        if self.model_name != other.model_name:
            return False
        if self.skills != other.skills:
            return False
        if self.params != other.params:
            return False
        if self.created_at != other.created_at:
            return False
        return self.updated_at == other.updated_at

    @classmethod
    def from_json(cls, json: dict, collection: CollectionBase):
        return cls(
            json['name'],
            json['model_name'],
            [Skill.from_json(skill) for skill in json['skills']],
            json['params'],
            json['created_at'],
            json['updated_at'],
            collection
        )


class Agents(CollectionBase):
    """Collection for agents"""
    def __init__(self, api, project: str, skills: Skills = None):
        self.api = api
        self.project = project
        self.skills = skills or Skills(self.api)

    def list(self) -> List[Agent]:
        """
        List available agents.

        :return: list of agents
        """
        data = self.api.agents(self.project)
        return [Agent.from_json(agent, self) for agent in data]

    def get(self, name: str) -> Agent:
        """
        Gets an agent by name.

        :param name: Name of the agent

        :return: agent with given name
        """
        data = self.api.agent(self.project, name)
        return Agent.from_json(data, self)

    def completion(self, name: str, messages: List[dict]) -> AgentCompletion:
        """
        Queries the agent for a completion.

        :param name: Name of the agent
        :param messages: List of messages to be sent to the agent

        :return: completion from querying the agent
        """
        data = self.api.agent_completion(self.project, name, messages)
        return AgentCompletion(data['message']['content'])

    def create(
            self,
            name: str,
            model: Model,
            skills: List[Union[Skill, str]] = None,
            params: dict = None) -> Agent:
        """
        Create new agent and return it

        :param name: Name of the agent to be created
        :param model: Model to be used by the agent
        :param skills: List of skills to be used by the agent. Currently only 'sql' is supported.
        :param params: Parameters for the agent

        :return: created agent object
        """
        skills = skills or []
        skill_names = []
        for skill in skills:
            if isinstance(skill, str):
                # Check if skill exists.
                _ = self.skills.get(skill)
                skill_names.append(skill)
                continue
            # Create the skill if it doesn't exist.
            _ = self.skills.create(skill.name, skill.type, skill.params)
            skill_names.append(skill.name)

        data = self.api.create_agent(self.project, name, model.name, skill_names, params)
        return Agent.from_json(data, self)

    def update(self, name: str, updated_agent: Agent):
        """
        Update an agent by name.

        :param name: Name of the agent to be updated
        :param updated_agent: Agent with updated fields

        :return: updated agent object
        """
        updated_skills = set()
        for skill in updated_agent.skills:
            if isinstance(skill, str):
                # Skill must exist.
                _ = self.skills.get(skill)
                updated_skills.add(skill)
                continue
            try:
                # Create the skill if it doesn't exist.
                _ = self.skills.get(skill.name)
            except HTTPError as e:
                if e.response.status_code != 404:
                    raise e
                # Doesn't exist
                _ = self.skills.create(skill.name, skill.type, skill.params)
            updated_skills.add(skill.name)

        existing_agent = self.api.agent(self.project, name)
        existing_skills = set([s.name for s in existing_agent['skills']])
        skills_to_add = updated_skills.difference(existing_skills)
        skills_to_remove = existing_skills.difference(updated_skills)
        data = self.api.update_agent(
            self.project,
            name,
            updated_agent.name,
            updated_agent.model_name,
            list(skills_to_add),
            list(skills_to_remove),
            updated_agent.params
        )
        return Agent.from_json(data, self)

    def delete(self, name: str):
        """
        Delete an agent by name.

        :param name: Name of the agent to be deleted
        """
        _ = self.api.delete_agent(self.project, name)
