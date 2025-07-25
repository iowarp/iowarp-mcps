"""
WRP Test Framework - Pytest-based test runner
Tests WRP (bin/wrp.py) by feeding prompts and validating JSON responses
"""
import json
import re
import yaml
import pytest
import asyncio
import sys
import subprocess
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from jsonschema import validate, ValidationError

# Global test yaml path prefix
TEST_YAML_PATH_PREFIX = "./bin/confs/test/"

class WRPTestConfig:
    """Configuration for a single WRP test"""

    def __init__(self, test_data: Dict[str, Any], provider: str = ""):
        self.name = test_data['name']
        self.description = test_data['description']
        # TBD: The 'mcps' and 'providers' fields here are duplicating info from the YAML
        # just to meet wrp.py expected config interface.
        # It would be nice to rework this if/when MCP discovery is reworked
        self.mcps = test_data['mcps']
        self.timeout = test_data.get('timeout', 30)
        self.wrp_configs = []

        # Use provider to set up test config path
        # <provider>_<mcp>.yaml
        # Format will need to be updated to support differing models
        # or multiple MCPs in a single test
        for mcp in self.mcps:
            self.wrp_configs.append(TEST_YAML_PATH_PREFIX + provider + "_" + mcp + ".yaml")

        # Handle both single-turn and multi-turn tests
        self.is_multi_turn = test_data.get('multi_turn', False)
        
        if self.is_multi_turn:
            self.turns = []
            for turn_data in test_data.get('turns', []):
                self.turns.append({
                    'prompt': turn_data['prompt'],
                    'expected_json': turn_data.get('expected_json', {}),
                    'json_schema': turn_data.get('json_schema', {})
                })
        else:
            # Single-turn test (backward compatibility)
            self.prompt = test_data['prompt']
            self.expected_json = test_data.get('expected_json', {})
            self.json_schema = test_data.get('json_schema', {})


class WRPTestRunner:
    """Runs WRP tests by executing wrp.py as subprocess"""
    
    # Global test iteration count for robustness checking
    TEST_ITERATION_COUNT = 1

    # Global wait time between iterations (seconds) to avoid rate limits
    ITERATION_WAIT_TIME = 5

    def __init__(self, test_yaml_path: str = "test_wrp.yaml", provider: str = ""):
        self.test_yaml_path = Path(test_yaml_path)
        self.wrp_script = Path("bin/wrp.py")
        self.tests = self._load_tests(provider)
    
    def _load_tests(self, provider) -> List[WRPTestConfig]:
        """Load test configurations from YAML"""
        if not self.test_yaml_path.exists():
            raise FileNotFoundError(f"Test file not found: {self.test_yaml_path}")
        
        with open(self.test_yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        
        return [WRPTestConfig(test, provider) for test in data.get('tests', [])]
    
    async def _execute_wrp_subprocess(self, wrp_config_path: str, input_text: str, timeout: int) -> str:
        """Execute WRP as subprocess with given input and return stdout"""
        try:
            # Build command
            cmd = [
                sys.executable, 
                str(self.wrp_script), 
                "--conf", wrp_config_path
            ]
            
            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path.cwd()
            )
            
            try:
                # Send input and get output
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=input_text.encode()),
                    timeout=timeout
                )
                
                if process.returncode != 0:
                    raise RuntimeError(f"WRP failed with code {process.returncode}: {stderr.decode()}")
                
                return stdout.decode().strip()
                
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise TimeoutError(f"WRP process timed out after {timeout} seconds")
                
        except Exception as e:
            raise RuntimeError(f"WRP execution failed: {e}")
    
    async def _run_wrp_with_prompt(self, wrp_config_path: str, prompt: str, timeout: int) -> str:
        """Run wrp.py with a specific prompt and return the response"""
        # Prepare input for WRP (prompt + quit command)
        full_input = f"{prompt}\nquit\n"
        
        # Execute WRP subprocess
        full_output = await self._execute_wrp_subprocess(wrp_config_path, full_input, timeout)
        
        # Extract and return the response content
        return self._extract_response_content(full_output)
    
    async def _run_wrp_multi_turn(self, wrp_config_path: str, turns: List[Dict[str, Any]], timeout: int) -> List[str]:
        """Run wrp.py with multiple prompts in sequence and return all responses"""
        # Prepare input for WRP (all prompts + quit command)
        all_input = ""
        for turn in turns:
            all_input += turn['prompt'] + "\n"
        all_input += "quit\n"
        
        # Execute WRP subprocess
        full_output = await self._execute_wrp_subprocess(wrp_config_path, all_input, timeout)
        
        # Extract and return multiple response contents
        return self._extract_multiple_responses(full_output, len(turns))
    
    def _extract_response_content(self, full_output: str) -> str:
        """Extract the actual response content from WRP output using regex"""
        # Pattern: Query: followed by response until next Query: or session end
        pattern = r'Query:\s*\n(.*?)(?=\nQuery:|\nSession with|\nExiting\.\.\.|\Z)'
        matches = re.findall(pattern, full_output, re.DOTALL)
        
        if matches:
            # Return the first substantial response (skip empty matches)
            for match in matches:
                cleaned = match.strip()
                if cleaned:
                    return cleaned
        
        # Fallback: return everything after first Query: if regex fails
        query_idx = full_output.find('Query:')
        if query_idx != -1:
            remaining = full_output[query_idx + 6:].strip()
            # Stop at session end markers
            for marker in ['\nQuery:', '\nSession with', '\nExiting...']:
                end_idx = remaining.find(marker)
                if end_idx != -1:
                    remaining = remaining[:end_idx]
            return remaining.strip()
        
        return full_output.strip()
    
    def _extract_multiple_responses(self, full_output: str, expected_count: int) -> List[str]:
        """Extract multiple response contents from WRP output using regex"""
        # Pattern: Query: followed by response until next Query: or session end
        pattern = r'Query:\s*\n(.*?)(?=\nQuery:|\nSession with|\nExiting\.\.\.|\Z)'
        matches = re.findall(pattern, full_output, re.DOTALL)
        
        responses = []
        for match in matches:
            cleaned = match.strip()
            if cleaned and not cleaned.startswith('Exiting') and not cleaned.startswith('Session with'):
                responses.append(cleaned)
        
        return responses
    
    def _extract_json_from_response(self, response: str) -> Dict[str, Any]:
        """Extract JSON from WRP response text with detailed error reporting"""
        extraction_attempts = []
        
        # Look for ```json blocks
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end != -1:
                json_text = response[start:end].strip()
                try:
                    return json.loads(json_text)
                except json.JSONDecodeError as e:
                    extraction_attempts.append(f"Markdown JSON blocks: JSONDecodeError - {e}")
            else:
                extraction_attempts.append("Markdown JSON blocks: Found opening ```json but no closing ```")
        
        # Look for generic ``` blocks
        if "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            if end != -1:
                json_text = response[start:end].strip()
                try:
                    return json.loads(json_text)
                except json.JSONDecodeError as e:
                    extraction_attempts.append(f"Generic code blocks: JSONDecodeError - {e}")
            else:
                extraction_attempts.append("Generic code blocks: Found opening ``` but no closing ```")
        
        # Look for JSON object patterns
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, response, re.DOTALL)
        
        if matches:
            for i, match in enumerate(matches):
                try:
                    return json.loads(match.strip())
                except json.JSONDecodeError as e:
                    extraction_attempts.append(f"Regex pattern match {i+1}: JSONDecodeError - {e}")
        else:
            extraction_attempts.append("Regex pattern search: No JSON-like patterns found")
        
        # Try parsing the entire response as JSON
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            extraction_attempts.append(f"Direct parsing: JSONDecodeError - {e}")
        
        # Create detailed error message
        error_msg = f"No valid JSON found in response. Attempted extractions:\n"
        for attempt in extraction_attempts:
            error_msg += f"  - {attempt}\n"
        error_msg += f"\nResponse content (first 500 chars): {response[:500]}"
        
        raise ValueError(error_msg)
    
    def _validate_json_response(self, response_json: Dict[str, Any], expected_json: Dict[str, Any], 
                              json_schema: Dict[str, Any]) -> None:
        """Validate JSON response against expected values and schema"""
        
        # Validate against schema if provided
        if json_schema:
            try:
                validate(instance=response_json, schema=json_schema)
            except ValidationError as e:
                raise AssertionError(f"JSON schema validation failed: {e.message}")
        
        # Validate against expected values if provided
        if expected_json:
            for key, expected_value in expected_json.items():
                if key not in response_json:
                    raise AssertionError(f"Missing expected key '{key}' in response")
                
                actual_value = response_json[key]
                if actual_value != expected_value:
                    raise AssertionError(
                        f"Expected {key}='{expected_value}', got '{actual_value}'"
                    )
    
    async def run_test(self, test_config: WRPTestConfig, iteration_count: int = None, wait_time: float = None) -> Dict[str, Any]:
        """Run a single test N times for robustness checking and return aggregated results"""
        if iteration_count is None:
            iteration_count = self.TEST_ITERATION_COUNT
        if wait_time is None:
            wait_time = self.ITERATION_WAIT_TIME
            
        iterations = []
        successful_runs = 0
        
        # Run the test N times per provider
        for iteration in range(iteration_count):
            for wrp_config in test_config.wrp_configs:
                try:
                    result = await self._run_single_test_iteration(test_config, wrp_config)
                    iterations.append(result)
                    if result['passed']:
                        successful_runs += 1
                except Exception as e:
                    iterations.append({
                        'passed': False,
                        'response': '',
                        'response_json': None,
                        'error': str(e),
                        'iteration': iteration + 1
                    })
                # Add wait time between iterations (except for the first one)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
        
        # Determine overall success (all iterations must pass)
        all_passed = successful_runs == iteration_count
        
        # Get the first successful result for backward compatibility
        successful_result = next((r for r in iterations if r['passed']), None)
        
        return {
            'passed': all_passed,
            'response': successful_result['response'] if successful_result else iterations[-1]['response'],
            'response_json': successful_result['response_json'] if successful_result else None,
            'error': None if all_passed else f"Only {successful_runs}/{iteration_count} iterations passed",
            'iterations': iterations,
            'successful_runs': successful_runs,
            'total_runs': iteration_count
        }
    
    async def _run_single_test_iteration(self, test_config: WRPTestConfig, wrp_config_path: str) -> Dict[str, Any]:
        """Run a single iteration of a test and return results"""
        try:
            if test_config.is_multi_turn:
                # Multi-turn test
                responses = await self._run_wrp_multi_turn(
                    wrp_config_path,
                    test_config.turns,
                    test_config.timeout
                )
                
                if len(responses) != len(test_config.turns):
                    raise RuntimeError(f"Expected {len(test_config.turns)} responses, got {len(responses)}")
                
                # Validate each turn's response
                all_response_json = []
                for i, (response, turn) in enumerate(zip(responses, test_config.turns)):
                    try:
                        response_json = self._extract_json_from_response(response)
                        self._validate_json_response(
                            response_json,
                            turn['expected_json'],
                            turn['json_schema']
                        )
                        all_response_json.append(response_json)
                    except Exception as e:
                        raise RuntimeError(f"Turn {i+1} failed: {e}")
                
                return {
                    'passed': True,
                    'response': responses,
                    'response_json': all_response_json,
                    'error': None
                }
            else:
                # Single-turn test (backward compatibility)
                response = await self._run_wrp_with_prompt(
                    wrp_config_path,
                    test_config.prompt,
                    test_config.timeout
                )
                
                # Extract JSON from response
                response_json = self._extract_json_from_response(response)
                
                # Validate the JSON response
                self._validate_json_response(
                    response_json, 
                    test_config.expected_json, 
                    test_config.json_schema
                )
                
                return {
                    'passed': True,
                    'response': response,
                    'response_json': response_json,
                    'error': None
                }
            
        except Exception as e:
            return {
                'passed': False,
                'response': getattr(e, 'response', ''),
                'response_json': None,
                'error': str(e)
            }


# Dynamic test generation from YAML
# Necessary for pytest
def pytest_generate_tests(metafunc):
    """Generate tests dynamically from YAML file"""
    if "test_config" in metafunc.fixturenames:
        runner = WRPTestRunner()
        test_configs = runner.tests
        test_ids = [test.name for test in test_configs]
        metafunc.parametrize("test_config", test_configs, ids=test_ids)


# Necessary for pytest
@pytest.mark.asyncio
async def test_wrp_yaml_test(test_config):
    """Run a single test from the YAML file"""
    runner = WRPTestRunner()
    result = await runner.run_test(test_config, runner.TEST_ITERATION_COUNT, runner.ITERATION_WAIT_TIME)
    
    assert result['passed'], f"Test '{test_config.name}' failed: {result['error']}"
    assert result['response_json'] is not None, "No JSON response received"

# Determine which LLM provider(s) are available in the test environment
def find_llm_providers() -> List[str]:
    providers = []

    if os.getenv("ANTHROPIC_API_KEY"):
        providers.append("claude")
    
    if os.getenv("GEMINI_API_KEY"):
        providers.append("gemini")

    return providers

if __name__ == "__main__":
    async def main():
        providers = find_llm_providers()

        if (len(providers) == 0):
            print(f"   No LLM providers found in environment. Populate 'ANTHROPIC_API_KEY' or GEMINI_API_KEY' env vars to run agent integration tests")
            sys.exit()

        for provider in providers:
            runner = WRPTestRunner(provider=provider)

            for test_config in runner.tests:
                print(f"\n=== Running {test_config.name} ({provider}, {runner.TEST_ITERATION_COUNT} iterations, {runner.ITERATION_WAIT_TIME}s wait) ===")
                result = await runner.run_test(test_config, runner.TEST_ITERATION_COUNT, runner.ITERATION_WAIT_TIME)
                print(f"Passed: {result['passed']} ({result['successful_runs']}/{result['total_runs']} iterations successful)")
                if not result['passed']:
                    print(f"Error: {result['error']}")
                if result['response_json']:
                    print(f"JSON: {json.dumps(result['response_json'], indent=2)}")

                # Show iteration details if any failed
                if result['successful_runs'] < result['total_runs']:
                    print(f" Iteration Details:")
                    for i, iteration in enumerate(result['iterations']):
                        print(f"  Iteration {i+1}: {'PASS' if iteration['passed'] else 'FAIL'}")
                        if not iteration['passed']:
                            print(f"    Error: {iteration['error']}")

    asyncio.run(main())