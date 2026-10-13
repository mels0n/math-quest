/**
 * Dependency rules for the frontend. They run in CI and fail the build.
 *
 * Layers, top to bottom: app > pages > widgets > features > entities > shared.
 * A layer may import only from layers strictly below it. Route files under
 * src/routes may import only from pages. Slices are reached through their index.
 */
const upward = (name, layer, above) => ({
  name,
  comment: `'${layer}' may only import from layers below it. Move the shared code down a layer.`,
  severity: 'error',
  from: { path: `^src/${layer}/` },
  to: { path: `^src/(${above.join('|')})/` },
});

module.exports = {
  forbidden: [
    upward('no-upward-import-from-pages', 'pages', ['app']),
    upward('no-upward-import-from-widgets', 'widgets', ['app', 'pages']),
    upward('no-upward-import-from-features', 'features', ['app', 'pages', 'widgets']),
    upward('no-upward-import-from-entities', 'entities', ['app', 'pages', 'widgets', 'features']),
    upward('no-upward-import-from-shared', 'shared', [
      'app',
      'pages',
      'widgets',
      'features',
      'entities',
    ]),
    {
      name: 'routes-import-pages-only',
      comment: 'Route files are thin: they may import only from pages.',
      severity: 'error',
      from: { path: '^src/routes/' },
      to: {
        path: '^src/',
        pathNot: ['^src/routes/', '^src/pages/', '^src/app\.d\.ts$'],
      },
    },
    {
      name: 'layers-do-not-import-routes',
      comment: 'Nothing imports from route files.',
      severity: 'error',
      from: { path: '^src/(app|pages|widgets|features|entities|shared)/' },
      to: { path: '^src/routes/' },
    },
    {
      name: 'no-cross-slice-import',
      comment: 'Slices on the same layer are siblings and must not import each other.',
      severity: 'error',
      from: { path: '^src/(pages|widgets|features|entities)/([^/]+)/' },
      to: { path: '^src/$1/(?!$2/)[^/]+/' },
    },
    {
      name: 'slice-public-api-only',
      comment: 'Import a slice through its index, never a file inside it.',
      severity: 'error',
      from: { pathNot: '^src/(pages|widgets|features|entities)/([^/]+)/' },
      to: {
        path: '^src/(pages|widgets|features|entities)/[^/]+/.+',
        pathNot: '^src/(pages|widgets|features|entities)/[^/]+/index\.(ts|js)$',
      },
    },
    {
      name: 'no-circular',
      comment: 'A cycle means a layer boundary has been crossed somewhere.',
      severity: 'error',
      from: {},
      to: { circular: true },
    },
  ],
  options: {
    doNotFollow: { path: 'node_modules' },
    tsConfig: { fileName: 'tsconfig.json' },
    tsPreCompilationDeps: true,
    exclude: { path: '\.(test|spec)\.(ts|js)$' },
    reporterOptions: { text: { highlightFocused: true } },
  },
};
