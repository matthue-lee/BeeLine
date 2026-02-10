#!/usr/bin/env python
"""Prompt template admin CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from beeline_ingestor.config import AppConfig
from beeline_ingestor.db import Database
from beeline_ingestor.models import PromptTemplate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage prompt templates")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="List prompt templates")
    list_parser.add_argument("--name", help="Filter by template name")

    create_parser = sub.add_parser("create", help="Create a new template")
    create_parser.add_argument("name")
    create_parser.add_argument("version")
    body_group = create_parser.add_mutually_exclusive_group(required=True)
    body_group.add_argument("--body")
    body_group.add_argument("--file")
    create_parser.add_argument("--metadata-json", help="JSON metadata", default="{}")

    activate_parser = sub.add_parser("activate", help="Activate a template version")
    activate_parser.add_argument("name")
    activate_parser.add_argument("version")
    activate_parser.add_argument("--traffic", type=int, default=100)

    deactivate_parser = sub.add_parser("deactivate", help="Deactivate a template")
    deactivate_parser.add_argument("name")
    deactivate_parser.add_argument("version")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = AppConfig.from_env()
    db = Database(config)
    with db.session() as session:
        if args.command == "list":
            query = session.query(PromptTemplate)
            if args.name:
                query = query.filter(PromptTemplate.name == args.name)
            templates = query.order_by(PromptTemplate.name, PromptTemplate.version).all()
            for tpl in templates:
                print(
                    f"{tpl.name} v{tpl.version} | active={tpl.is_active} | traffic={tpl.traffic_allocation}%"
                )
        elif args.command == "create":
            if args.body:
                body = args.body
            else:
                body = Path(args.file).read_text()
            metadata = json.loads(args.metadata_json)
            tpl = PromptTemplate(
                name=args.name,
                version=args.version,
                body=body,
                metadata_json=metadata,
                is_active=False,
            )
            session.add(tpl)
            print(f"Created template {args.name} v{args.version}")
        elif args.command == "activate":
            session.query(PromptTemplate).filter(PromptTemplate.name == args.name).update(
                {PromptTemplate.is_active: False}
            )
            tpl = (
                session.query(PromptTemplate)
                .filter(PromptTemplate.name == args.name, PromptTemplate.version == args.version)
                .one()
            )
            tpl.is_active = True
            tpl.traffic_allocation = args.traffic
            print(f"Activated {args.name} v{args.version} with {args.traffic}% traffic")
        elif args.command == "deactivate":
            tpl = (
                session.query(PromptTemplate)
                .filter(PromptTemplate.name == args.name, PromptTemplate.version == args.version)
                .one()
            )
            tpl.is_active = False
            print(f"Deactivated {args.name} v{args.version}")


if __name__ == "__main__":
    main()
