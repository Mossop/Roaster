import os, ConfigParser, sys, svn.core, svn.client, svn.wc

def createSVNContext():
  ctx = svn.client.svn_client_ctx_t()
  providers = []
  providers.append(svn.client.get_simple_provider())
  providers.append(svn.client.get_username_provider())
  providers.append(svn.client.get_ssl_server_trust_file_provider())
  providers.append(svn.client.get_ssl_client_cert_file_provider())
  providers.append(svn.client.get_ssl_client_cert_pw_file_provider())
  ctx.auth_baton = svn.core.svn_auth_open(providers)
  ctx.config = svn.core.svn_config_get_config(None)
  return ctx

def getSVNRevision(num):
  value = svn.core.svn_opt_revision_value_t()
  value.number = num
  revision = svn.core.svn_opt_revision_t()
  revision.kind = svn.core.svn_opt_revision_number
  revision.value = value
  return revision

def getSVNHeadRevision():
  revision = svn.core.svn_opt_revision_t()
  revision.kind = svn.core.svn_opt_revision_head
  return revision

def changeRevision(ctx, dir, revision):
  path = svn.core.svn_path_canonicalize(dir)
  adm_access = svn.wc.adm_probe_open(None, path, False, False)
  entry = svn.wc.entry(path, adm_access, False)
  if (revision) and (entry.revision == int(revision)):
    return False
  if revision:
    rev = getSVNRevision(int(revision))
  else:
    rev = getSVNHeadRevision()
  newrev = svn.client.update(path, rev, True, ctx)
  if entry.revision != newrev:
    return True
  return False

def getRevision(dir):
  if os.path.isdir(os.path.join(dir, ".svn")):
    path = svn.core.svn_path_canonicalize(dir)
    adm_access = svn.wc.adm_probe_open(None, path, False, False)
    entry = svn.wc.entry(path, adm_access, False)
    return entry.revision
  return None

def getDirs(basedir, dirs, versioned = False):
  results = []
  for dir in dirs:
    if os.path.isdir(os.path.join(basedir, dir)):
      path = os.path.join(basedir, dir)
    else:
      continue
    if versioned:
      if not os.path.isdir(os.path.join(path, ".svn")):
        continue
    if os.path.exists(os.path.join(path, "build", "xpibuild.py")):
      results.append(path)

  return results

def build(dir, release, outputdir):
  sys.path.append(os.path.join(dir, "build"))
  xpibuild = __import__("xpibuild")
  builder = xpibuild.XPIBuilder(dir)
  builder.release = True
  if not release:
    revision = getRevision(dir)
    builder.buildid = "rev" + str(revision)

  print "  Building..."
  try:
    builder.init()
    if outputdir:
      builder.outputdir = outputdir.replace("${name}", builder.settings['name'])
    builder.clean()
    builder.build()
    builder.package()
  except:
    print "  Build failed"
  sys.path = sys.path[:-1]

def main():
  config = ConfigParser.ConfigParser()
  inifile = os.path.join(os.path.dirname(os.path.dirname(__file__)), "roaster.ini")
  if os.path.exists(inifile):
    config.read(inifile)

  from optparse import OptionParser
  parser = OptionParser("Usage: %prog [options] [directory1] [directory2] .. [directoryn]")
  parser.add_option("-u", "--update", action="store_true", default = False,
                    help="update to the latest revision, only build if there was a change")
  parser.add_option("-r", "--revision", default = None,
                    help="update to a specific revision, only build if there was a change")
  parser.add_option("-f", "--force", action="store_true", default = False,
                    help="force building even if the update made no change")
  parser.add_option("-l", "--release", action="store_true", default = False,
                    help="create release builds with no build identifier")
  parser.add_option("-b", "--basedir", default = None,
                    help="set the base directory of the items")
  parser.add_option("-q", "--quiet", action="store_true", default = False,
                    help="Only display messages when something happens")
  (options, items) = parser.parse_args()

  if options.basedir:
    basedir = options.basedir
  else:
    if config.has_option("paths", "roastdir"):
      basedir = config.get("paths", "roastdir")
    else:
      parser.error("no base directory specified on command line or in configuration")
      return

  if not os.path.exists(basedir):
    parser.error("base directory does not exist")
    return

  if options.update and options.revision:
    parser.error("cannot give both -u and -r at the same time")
    return

  if len(items) == 0:
    roasts = getDirs(basedir, os.listdir(basedir), options.update or options.revision)
  else:
    roasts = getDirs(basedir, items, options.update or options.revision)
    if len(roasts) < len(items):
      parser.error("invalid directories specified")
      return

  if len(roasts) == 0:
    parser.error("nothing to do")
    return

  if os.path.exists(os.path.join(basedir, "roast.lock")):
    parser.error("directory is locked")
    return

  if options.release:
    target = "releasedir"
  else:
    target = "outputdir"
  if config.has_option("paths", target):
    outputdir = config.get("paths", target)
  else:
    outputdir = None

  os.mkdir(os.path.join(basedir, "roast.lock"))
  try:
    ctx = createSVNContext()
    for dir in roasts:
      if options.revision or options.update:
        if ((not changeRevision(ctx, dir, options.revision)) and
           (not options.force)):
          if not options.quiet:
            print "Skipping " + dir + ", No change"
          continue
      print "Roasting " + dir
      build(dir, options.release, outputdir)
  finally:
    os.rmdir(os.path.join(basedir, "roast.lock"))

main()
