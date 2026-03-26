"""Minimal schema-valid YAML for discovery / bootstrap tests."""

MIN_PRODUCT = """info:
  name: "Test Product"
  description: "Test"
  slug: {slug}
  developer_cli: tp
  db_name: test_db
  base_port: 8080
organization:
  name: "Test Org"
  email: test@example.com
  founded: 2024
  slug: testorg
  git_host: https://github.com
  git_org: testorg
  docker_host: ghcr.io
  docker_org: testorg
"""

MIN_ARCH = """architecture:
  environments:
    - name: dev
  domains:
    - name: dom1
      description: "Domain one"
      data_domains:
        controls: []
        creates: []
        consumes: []
      repos:
        - name: svc1
          description: "Service"
          type: api
          port: 8080
          template: agile-learning-institute/stage0_template_flask_mongo
          publish: make
"""

MIN_CATALOG = """data_dictionaries:
  - name: dict1
    description: "One dictionary"
"""


def write_three_specs(spec_dir, slug: str = "myslug") -> None:
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "product.yaml").write_text(
        MIN_PRODUCT.format(slug=slug), encoding="utf-8"
    )
    (spec_dir / "architecture.yaml").write_text(MIN_ARCH, encoding="utf-8")
    (spec_dir / "catalog.yaml").write_text(MIN_CATALOG, encoding="utf-8")
