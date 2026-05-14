"""Database query functions using recursive CTEs for dependency analysis.

This module provides asyncpg-based query functions for analyzing symbol
dependencies, finding cycles, and computing transitive closures.
"""

from typing import List, Dict, Any, Optional, Set, Tuple
import asyncpg


async def get_transitive_deps(
    conn: asyncpg.Connection,
    full_name: str,
    max_depth: int = 5
) -> List[Dict[str, Any]]:
    """Get all transitive dependencies of a symbol up to max_depth.
    
    Uses a recursive CTE to traverse the dependency graph starting from
    the given symbol and following outgoing edges.
    
    Args:
        conn: asyncpg database connection
        full_name: Fully qualified name of the symbol
        max_depth: Maximum depth to traverse (default: 5)
        
    Returns:
        List of dicts containing:
            - symbol_id: Target symbol ID
            - full_name: Target symbol full name
            - name: Target symbol name
            - kind: Target symbol kind
            - depth: Distance from source symbol
            - path: Array of symbol IDs in the path
            - dependency_type: Type of dependency edge
    """
    query = """
        WITH RECURSIVE dep_tree AS (
            -- Base case: start with the source symbol
            SELECT
                s.id AS symbol_id,
                s.full_name,
                s.name,
                s.kind,
                0 AS depth,
                ARRAY[s.id] AS path,
                NULL::dependency_type AS dependency_type
            FROM symbols s
            WHERE s.full_name = $1
            
            UNION ALL
            
            -- Recursive case: follow dependencies
            SELECT
                target.id AS symbol_id,
                target.full_name,
                target.name,
                target.kind,
                dt.depth + 1 AS depth,
                dt.path || target.id AS path,
                d.dependency_type
            FROM dep_tree dt
            INNER JOIN dependencies d ON dt.symbol_id = d.source_symbol_id
            INNER JOIN symbols target ON d.target_symbol_id = target.id
            WHERE 
                dt.depth < $2
                AND NOT (target.id = ANY(dt.path))  -- Prevent cycles
        )
        SELECT
            symbol_id,
            full_name,
            name,
            kind::text,
            depth,
            path,
            dependency_type::text
        FROM dep_tree
        WHERE depth > 0  -- Exclude the source symbol itself
        ORDER BY depth, full_name;
    """
    
    rows = await conn.fetch(query, full_name, max_depth)
    return [dict(row) for row in rows]


async def get_reverse_deps(
    conn: asyncpg.Connection,
    full_name: str,
    max_depth: int = 5
) -> List[Dict[str, Any]]:
    """Get all symbols that depend on the given symbol (reverse dependencies).
    
    Uses a recursive CTE to traverse the dependency graph in reverse,
    finding all symbols that directly or indirectly depend on the target.
    
    Args:
        conn: asyncpg database connection
        full_name: Fully qualified name of the symbol
        max_depth: Maximum depth to traverse (default: 5)
        
    Returns:
        List of dicts containing:
            - symbol_id: Source symbol ID that depends on target
            - full_name: Source symbol full name
            - name: Source symbol name
            - kind: Source symbol kind
            - depth: Distance from target symbol
            - path: Array of symbol IDs in the reverse path
            - dependency_type: Type of dependency edge
    """
    query = """
        WITH RECURSIVE reverse_dep_tree AS (
            -- Base case: start with the target symbol
            SELECT
                s.id AS symbol_id,
                s.full_name,
                s.name,
                s.kind,
                0 AS depth,
                ARRAY[s.id] AS path,
                NULL::dependency_type AS dependency_type
            FROM symbols s
            WHERE s.full_name = $1
            
            UNION ALL
            
            -- Recursive case: follow reverse dependencies
            SELECT
                source.id AS symbol_id,
                source.full_name,
                source.name,
                source.kind,
                rdt.depth + 1 AS depth,
                rdt.path || source.id AS path,
                d.dependency_type
            FROM reverse_dep_tree rdt
            INNER JOIN dependencies d ON rdt.symbol_id = d.target_symbol_id
            INNER JOIN symbols source ON d.source_symbol_id = source.id
            WHERE 
                rdt.depth < $2
                AND NOT (source.id = ANY(rdt.path))  -- Prevent cycles
        )
        SELECT
            symbol_id,
            full_name,
            name,
            kind::text,
            depth,
            path,
            dependency_type::text
        FROM reverse_dep_tree
        WHERE depth > 0  -- Exclude the target symbol itself
        ORDER BY depth, full_name;
    """
    
    rows = await conn.fetch(query, full_name, max_depth)
    return [dict(row) for row in rows]


async def find_cycles(
    conn: asyncpg.Connection,
    project_id: int,
    max_cycle_length: int = 10
) -> List[Dict[str, Any]]:
    """Find all dependency cycles in the project.
    
    Uses a recursive CTE to detect cycles in the dependency graph.
    A cycle exists when a symbol transitively depends on itself.
    
    Args:
        conn: asyncpg database connection
        project_id: Project ID to search for cycles
        max_cycle_length: Maximum cycle length to detect (default: 10)
        
    Returns:
        List of dicts containing:
            - cycle_start_id: Symbol ID where cycle starts
            - cycle_start_name: Full name of cycle start symbol
            - cycle_length: Number of edges in the cycle
            - cycle_path: Array of symbol IDs forming the cycle
            - cycle_names: Array of symbol names in the cycle
    """
    query = """
        WITH RECURSIVE cycle_detection AS (
            -- Base case: all symbols in the project
            SELECT
                s.id AS start_id,
                s.full_name AS start_name,
                s.id AS current_id,
                1 AS depth,
                ARRAY[s.id] AS path,
                ARRAY[s.full_name] AS name_path
            FROM symbols s
            WHERE s.project_id = $1
            
            UNION ALL
            
            -- Recursive case: follow dependencies
            SELECT
                cd.start_id,
                cd.start_name,
                target.id AS current_id,
                cd.depth + 1 AS depth,
                cd.path || target.id AS path,
                cd.name_path || target.full_name AS name_path
            FROM cycle_detection cd
            INNER JOIN dependencies d ON cd.current_id = d.source_symbol_id
            INNER JOIN symbols target ON d.target_symbol_id = target.id
            WHERE 
                cd.depth < $2
                AND (
                    -- Continue if no cycle detected yet
                    target.id != cd.start_id
                    -- Or if we just detected a cycle (to capture it)
                    OR cd.depth = 1
                )
                AND NOT (target.id = ANY(cd.path[2:]))  -- Avoid intermediate duplicates
        )
        SELECT DISTINCT
            start_id AS cycle_start_id,
            start_name AS cycle_start_name,
            depth AS cycle_length,
            path AS cycle_path,
            name_path AS cycle_names
        FROM cycle_detection
        WHERE 
            current_id = start_id  -- Cycle detected
            AND depth > 1  -- Must have at least one edge
        ORDER BY depth, start_name;
    """
    
    rows = await conn.fetch(query, project_id, max_cycle_length)
    return [dict(row) for row in rows]


async def top_symbols_by_usage(
    conn: asyncpg.Connection,
    project_id: int,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Get the most referenced symbols in a project.
    
    Identifies symbols with the highest number of incoming dependencies,
    which are the most heavily used symbols in the codebase.
    
    Args:
        conn: asyncpg database connection
        project_id: Project ID to analyze
        limit: Maximum number of symbols to return (default: 10)
        
    Returns:
        List of dicts containing:
            - symbol_id: Symbol ID
            - full_name: Symbol full name
            - name: Symbol short name
            - kind: Symbol kind
            - usage_count: Number of incoming dependencies
            - file_path: Relative path of file containing the symbol
            - module_name: Module name
    """
    query = """
        SELECT
            s.id AS symbol_id,
            s.full_name,
            s.name,
            s.kind::text,
            COUNT(d.id) AS usage_count,
            f.relative_path AS file_path,
            f.module_name
        FROM symbols s
        INNER JOIN files f ON s.file_id = f.id
        LEFT JOIN dependencies d ON s.id = d.target_symbol_id
        WHERE s.project_id = $1
        GROUP BY s.id, s.full_name, s.name, s.kind, f.relative_path, f.module_name
        HAVING COUNT(d.id) > 0
        ORDER BY usage_count DESC, s.full_name
        LIMIT $2;
    """
    
    rows = await conn.fetch(query, project_id, limit)
    return [dict(row) for row in rows]


async def get_symbol_centrality(
    conn: asyncpg.Connection,
    project_id: int,
    min_connections: int = 5
) -> List[Dict[str, Any]]:
    """Get symbols with high centrality (many connections).
    
    Finds symbols that are highly connected in the dependency graph,
    indicating central or important components in the architecture.
    
    Args:
        conn: asyncpg database connection
        project_id: Project ID to analyze
        min_connections: Minimum total connections to include (default: 5)
        
    Returns:
        List of dicts containing symbol info with connection counts
    """
    query = """
        SELECT
            symbol_id,
            full_name,
            name,
            kind::text,
            outgoing_dependencies,
            incoming_dependencies,
            total_connections,
            fan_out_ratio
        FROM dependency_stats
        WHERE 
            project_id = $1
            AND total_connections >= $2
        ORDER BY total_connections DESC, incoming_dependencies DESC;
    """
    
    rows = await conn.fetch(query, project_id, min_connections)
    return [dict(row) for row in rows]


async def get_module_complexity(
    conn: asyncpg.Connection,
    project_id: int,
    order_by: str = "total_symbols"
) -> List[Dict[str, Any]]:
    """Get module complexity metrics ordered by specified field.
    
    Args:
        conn: asyncpg database connection
        project_id: Project ID to analyze
        order_by: Field to order by (default: "total_symbols")
            Options: "total_symbols", "theorem_count", "avg_symbol_length_lines"
        
    Returns:
        List of dicts containing module metrics
    """
    # Validate order_by to prevent SQL injection
    valid_order_fields = {
        "total_symbols", "theorem_count", "def_count", 
        "avg_symbol_length_lines", "documentation_coverage_pct"
    }
    if order_by not in valid_order_fields:
        order_by = "total_symbols"
    
    query = f"""
        SELECT
            file_id,
            module_name,
            total_symbols,
            theorem_count,
            def_count,
            instance_count,
            inductive_count,
            structure_count,
            class_count,
            avg_symbol_length_lines,
            max_symbol_length_lines,
            public_symbols,
            deprecated_symbols,
            documented_symbols,
            documentation_coverage_pct
        FROM module_metrics
        WHERE project_id = $1
        ORDER BY {order_by} DESC NULLS LAST, module_name;
    """
    
    rows = await conn.fetch(query, project_id)
    return [dict(row) for row in rows]


# Helper function to establish connection
async def get_connection(database_url: str) -> asyncpg.Connection:
    """Create a database connection from a URL.
    
    Args:
        database_url: PostgreSQL connection URL
        
    Returns:
        asyncpg Connection object
    """
    return await asyncpg.connect(database_url)


# Example usage
async def example_usage():
    """Example of how to use these query functions."""
    import os
    
    database_url = os.getenv('DATABASE_URL', 'postgresql://lean4:lean4_dev_password@localhost:5432/lean4_automata')
    
    conn = await get_connection(database_url)
    
    try:
        # Get transitive dependencies
        deps = await get_transitive_deps(conn, 'Mathlib.Data.List.Basic.append', max_depth=3)
        print(f"Found {len(deps)} transitive dependencies")
        
        # Get reverse dependencies
        reverse = await get_reverse_deps(conn, 'Mathlib.Data.List.Basic.length', max_depth=3)
        print(f"Found {len(reverse)} symbols depending on length")
        
        # Find cycles in project 1
        cycles = await find_cycles(conn, project_id=1)
        print(f"Found {len(cycles)} cycles")
        
        # Get top used symbols
        top = await top_symbols_by_usage(conn, project_id=1, limit=10)
        print(f"Top 10 most used symbols:")
        for sym in top:
            print(f"  {sym['full_name']}: {sym['usage_count']} references")
            
    finally:
        await conn.close()


if __name__ == '__main__':
    import asyncio
    asyncio.run(example_usage())
