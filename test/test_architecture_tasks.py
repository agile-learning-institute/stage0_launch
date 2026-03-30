from stage0_launch.architecture_tasks import (
    collect_all_launch_tasks,
    collect_launch_tasks_for_services,
    template_repo_basename,
)
from test.specs_minimal import write_three_specs


def test_template_repo_basename():
    assert (
        template_repo_basename("agile-learning-institute/stage0_template_foo")
        == "stage0_template_foo"
    )
    assert template_repo_basename("") == ""
    assert template_repo_basename("null") == ""


def test_collect_all_launch_tasks(tmp_path):
    spec = tmp_path / "specs"
    write_three_specs(spec, slug="myslug")
    tasks = collect_all_launch_tasks(spec / "architecture.yaml")
    assert len(tasks) == 1
    assert tasks[0].svc == "dom1"
    assert tasks[0].repo_name == "svc1"
    assert "stage0_template_flask_mongo" in tasks[0].template


def test_collect_launch_tasks_for_services_order(tmp_path):
    """Domain order follows the services string, not YAML file order."""
    arch_text = """architecture:
  environments:
    - name: dev
  domains:
    - name: first
      description: "1"
      data_domains:
        controls: []
        creates: []
        consumes: []
      repos:
        - name: a_api
          description: "A"
          type: api
          port: 1
          template: agile-learning-institute/stage0_template_flask_mongo
          publish: make
    - name: second
      description: "2"
      data_domains:
        controls: []
        creates: []
        consumes: []
      repos:
        - name: b_api
          description: "B"
          type: api
          port: 2
          template: agile-learning-institute/stage0_template_flask_mongo
          publish: make
"""
    spec = tmp_path / "specs"
    write_three_specs(spec, slug="myslug")
    (spec / "architecture.yaml").write_text(arch_text, encoding="utf-8")

    ordered = collect_launch_tasks_for_services(
        spec / "architecture.yaml", "second first"
    )
    assert [t.repo_name for t in ordered] == ["b_api", "a_api"]
