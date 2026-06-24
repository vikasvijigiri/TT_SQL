from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class PromptNode(BaseModel):
    """
    Structured internal representation of a prompt section or component.
    Enables intelligent deduplication, selective rendering, and priority trimming.
    """

    section_type: str = Field(
        description="Category of the node: rules, schema, templates, directives, lessons, query, metadata, or system."
    )
    name: str = Field(
        description="Unique identifier for the section (e.g., 'dynamic_schema', 'dialect_rules')."
    )
    content: Union[str, Dict[str, Any], List[Any]] = Field(
        description="Raw or structured content of the section."
    )
    priority: int = Field(
        default=5,
        description="Priority rank: 1=highest (schema/joins/rules), 5=lowest (verbose examples/metadata).",
    )
    droppable: bool = Field(
        default=True,
        description="Whether this section can be trimmed or dropped if budget is exceeded.",
    )
    semantic_value: float = Field(
        default=1.0,
        description="Relevance score (0.0 to 1.0) derived from query context matching.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context or telemetry tags."
    )

    def render(self) -> str:
        """Renders the node content to a string."""
        if isinstance(self.content, str):
            return self.content.strip()
        elif isinstance(self.content, list):
            return "\n".join(str(item) for item in self.content).strip()
        elif isinstance(self.content, dict):
            return "\n".join(f"{k}: {v}" for k, v in self.content.items()).strip()
        return str(self.content).strip()


class PromptAST(BaseModel):
    """
    Abstract Syntax Tree managing the hierarchy and sequence of prompt nodes.
    """

    root_nodes: List[PromptNode] = Field(
        default_factory=list, description="Ordered sequence of prompt nodes in the AST."
    )

    def add_node(self, node: PromptNode) -> None:
        """Appends a new node to the AST, replacing any node with the exact same name."""
        existing_idx = self.get_node_index(node.name)
        if existing_idx is not None:
            self.root_nodes[existing_idx] = node
        else:
            self.root_nodes.append(node)

    def get_node(self, name: str) -> Optional[PromptNode]:
        """Retrieves a node by its unique name."""
        for n in self.root_nodes:
            if n.name == name:
                return n
        return None

    def get_node_index(self, name: str) -> Optional[int]:
        """Retrieves the index of a node by its unique name."""
        for i, n in enumerate(self.root_nodes):
            if n.name == name:
                return i
        return None

    def get_nodes_by_type(self, section_type: str) -> List[PromptNode]:
        """Retrieves all nodes matching a specific section type."""
        return [n for n in self.root_nodes if n.section_type == section_type]

    def remove_node(self, name: str) -> bool:
        """Removes a node by its unique name. Returns True if removed."""
        idx = self.get_node_index(name)
        if idx is not None:
            self.root_nodes.pop(idx)
            return True
        return False

    def render_all(self, separator: str = "\n\n") -> str:
        """Renders all active nodes in their sequence order."""
        rendered = [node.render() for node in self.root_nodes if node.render()]
        return separator.join(rendered).strip()
