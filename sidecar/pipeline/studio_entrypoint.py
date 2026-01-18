import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from sidecar.pipeline.default import DefaultPipeline
from sidecar.pipeline.types import PipelineConfig

# Initialize config
# In studio mode, we don't have access to the real VaultBrain/Plugins, 
# so we run with a barebones config.
config = PipelineConfig(
    model="gpt-4o",
    temperature=0.7
)

# Initialize Pipeline
pipeline = DefaultPipeline(config)

# Export the compiled graph
graph = pipeline.graph
