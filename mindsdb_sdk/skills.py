from typing import List

from mindsdb_sdk.utils.objects_collection import CollectionBase


class Skill():
    """Represents a MindsDB skill"""
    def __init__(
            self,
            name: str,
            type: str,
            params: dict = None):
        self.name = name
        self.type = type
        self.params = params or {}

    def __eq__(self, other):
        if self.name != other.name:
            return False
        if self.type != other.type:
            return False
        return self.params == other.params

    def __repr__(self):
        return f'{self.__class__.__name__}(name: {self.name})'

    @classmethod
    def from_json(cls, json: dict):
        return cls(json['name'], json['type'], json['params'])


class SQLSkill(Skill):
    """Represents a MindsDB skill for agents to interact with MindsDB databases"""
    def __init__(self, name: str, tables: List[str], database: str):
        params = {
            'database': database,
            'tables': tables,
        }
        super().__init__(name, 'sql', params)


class Skills(CollectionBase):
    """Collection for skills"""
    def __init__(self, api, project: str):
        self.api = api
        self.project = project

    def list(self) -> List[Skill]:
        """
        List available skills.

        :return: list of skills
        """
        data = self.api.skills(self.project)
        return [Skill.from_json(skill) for skill in data]

    def get(self, name: str) -> Skill:
        """
        Gets a skill by name.

        :param name: name of the skill

        :return: skill with the given name
        """
        data = self.api.skill(self.project, name)
        return Skill.from_json(data)

    def create(self, name: str, type: str, params: dict = None) -> Skill:
        """
        Create new skill and return it

        :param name: Name of the skill to be created
        :param type: Type of the skill to be created
        :param params: Parameters for the skill to be created

        :return: created skill object
        """
        _ = self.api.create_skill(self.project, name, type, params)
        if type == 'sql':
            return SQLSkill(name, params['tables'], params['database'])
        return Skill(name, type, params)

    def update(self, name: str, updated_skill: Skill) -> Skill:
        """
        Update a skill by name.

        param name: Name of the skill to be updated
        :param updated_skill: Skill with updated fields

        :return: updated skillobject
        """
        data = self.api.update_skill(self.project, name, updated_skill.name, updated_skill.type, updated_skill.params)
        return Skill.from_json(data)

    def delete(self, name: str):
        """
        Delete a skill by name.

        :param name: Name of the skill to be deleted
        """
        _ = self.api.delete_skill(self.project, name)