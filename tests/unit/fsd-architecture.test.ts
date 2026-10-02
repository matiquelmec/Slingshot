import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

function getFilesRecursively(dir: string): string[] {
  let results: string[] = [];
  if (!fs.existsSync(dir)) return results;
  const list = fs.readdirSync(dir);
  for (const file of list) {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    if (stat && stat.isDirectory()) {
      results = results.concat(getFilesRecursively(filePath));
    } else if (file.endsWith('.ts') || file.endsWith('.tsx')) {
      results.push(filePath);
    }
  }
  return results;
}

describe('FSD Architectural Unidirectional Hierarchy Guard', () => {
  const rootSrc = path.resolve(import.meta.dirname, '../../src');
  const sharedDir = path.join(rootSrc, 'shared');
  const entitiesDir = path.join(rootSrc, 'entities');

  it('enforces that shared layer NEVER imports from entities, features, or app', () => {
    const sharedFiles = getFilesRecursively(sharedDir);
    expect(sharedFiles.length).toBeGreaterThan(0);

    const forbiddenPatterns = [
      /from\s+['"]@\/entities/i,
      /from\s+['"]@\/features/i,
      /from\s+['"]@\/app/i,
      /from\s+['"]\.\.\/entities/i,
      /from\s+['"]\.\.\/features/i,
      /from\s+['"]\.\.\/app/i,
    ];

    for (const file of sharedFiles) {
      const content = fs.readFileSync(file, 'utf-8');
      for (const pattern of forbiddenPatterns) {
        const matches = pattern.test(content);
        expect(
          matches,
          `FSD Layer Violation: Shared file "${path.basename(file)}" must not import upper layers (matched ${pattern})`
        ).toBe(false);
      }
    }
  });

  it('enforces that entities layer NEVER imports from features or app', () => {
    const entityFiles = getFilesRecursively(entitiesDir);
    expect(entityFiles.length).toBeGreaterThan(0);

    const forbiddenPatterns = [
      /from\s+['"]@\/features/i,
      /from\s+['"]@\/app/i,
      /from\s+['"]\.\.\/features/i,
      /from\s+['"]\.\.\/app/i,
    ];

    for (const file of entityFiles) {
      const content = fs.readFileSync(file, 'utf-8');
      for (const pattern of forbiddenPatterns) {
        const matches = pattern.test(content);
        expect(
          matches,
          `FSD Layer Violation: Entity file "${path.basename(file)}" must not import upper layers (matched ${pattern})`
        ).toBe(false);
      }
    }
  });
});
