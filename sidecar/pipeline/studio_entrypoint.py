import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from sidecar.pipeline.default import DefaultPipeline
from sidecar.pipeline.manager import PipelineManager
from sidecar.pipeline.types import PipelineConfig

# initialize manager and config
# In studio mode, we don't have access to the real VaultBrain/Plugins, 
# so we run with a barebones manager.
manager = PipelineManager()
config = PipelineConfig(
    model="gpt-4o",
    temperature=0.7
)

# Initialize Pipeline
pipeline = DefaultPipeline(manager, config)

# Export the compiled graph
graph = pipeline.graph
