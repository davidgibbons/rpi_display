#!/usr/bin/python
# Uses pygame, pyyaml, python-twitter libraries

import os, pygame, time, random, twitter, socket, fcntl, struct, yaml, logging, HTMLParser

logging.basicConfig()

logger = logging.getLogger ('rpi_twitter')

#
# config loader
#
def load_config_file (config_file):
    try:
        cfg = yaml.load (file (config_file))
    except Exception as e:
        logger.error ("Syntax error in configuration file:")
        logger.error ("\t=> %s" % e)
    else:
        return cfg

#
# application configuration
#
def configure (config_file):
    cfg = load_config_file (config_file)
    if not cfg:
        logger.error ("Aborting")
        raise SystemExit
    return cfg


def get_ip_address():
    return [(s.connect(('8.8.8.8', 80)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]


modify_time = None

def autoreload_config_file (config_file):
    logger.warn ('autoreloading config')
    modified = os.stat (config_file).st_mtime
    global modify_time
    if modify_time == modified:
        logger.error ("Skipping reload, previous configuration remains in effect.")
        return
    elif not modify_time:
        modify_time = modified
    else:
        logger.warn ('Modified %s, reloading configuration' % config_file)
        modify_time = modified
    return configure (config_file)


def render_textrect(string, font, rect, text_color, background_color, justification=0):
    """Returns a surface containing the passed text string, reformatted
    to fit within the given rect, word-wrapping as necessary. The text
    will be anti-aliased.

    Takes the following arguments:

    string - the text you wish to render. \n begins a new line.
    font - a Font object
    rect - a rectstyle giving the size of the surface requested.
    text_color - a three-byte tuple of the rgb value of the
                 text color. ex (0, 0, 0) = BLACK
    background_color - a three-byte tuple of the rgb value of the surface.
    justification - 0 (default) left-justified
                    1 horizontally centered
                    2 right-justified

    Returns the following values:

    Success - a surface object with the text rendered onto it.
    Failure - raises a TextRectException if the text won't fit onto the surface.
    # This function by Author: David Clark (da_clark at shaw.ca)
    """

    final_lines = []

    requested_lines = string.splitlines()

    # Create a series of lines that will fit on the provided
    # rectangle.

    for requested_line in requested_lines:
        if font.size(requested_line)[0] > rect.width:
            words = requested_line.split(' ')
            # if any of our words are too long to fit, return.
            for word in words:
                if font.size(word)[0] >= rect.width:
                    raise TextRectException, "The word " + word + " is too long to fit in the rect passed."
            # Start a new line
            accumulated_line = ""
            for word in words:
                test_line = accumulated_line + word + " "
                # Build the line while the words fit.
                if font.size(test_line)[0] < rect.width:
                    accumulated_line = test_line
                else:
                    final_lines.append(accumulated_line)
                    accumulated_line = word + " "
            final_lines.append(accumulated_line)
        else:
            final_lines.append(requested_line)

    # Let's try to write the text out on the surface.

    surface = pygame.Surface(rect.size)
    surface.fill(background_color)

    accumulated_height = 0
    for line in final_lines:
        if accumulated_height + font.size(line)[1] >= rect.height:
            raise TextRectException, "Once word-wrapped, the text string was too tall to fit in the rect."
        if line != "":
            tempsurface = font.render(line, 1, text_color)
            if justification == 0:
                surface.blit(tempsurface, (0, accumulated_height))
            elif justification == 1:
                surface.blit(tempsurface, ((rect.width - tempsurface.get_width()) / 2, accumulated_height))
            elif justification == 2:
                surface.blit(tempsurface, (rect.width - tempsurface.get_width(), accumulated_height))
            else:
                raise TextRectException, "Invalid justification argument: " + str(justification)
        accumulated_height += font.size(line)[1]

    return surface

class TextRectException:
    def __init__(self, message = None):
        self.message = message
    def __str__(self):
        return self.message



class pyscope:
    screen = None;

    def __init__(self):
        "Ininitializes a new pygame screen using the framebuffer"
        # Based on "Python GUI in Linux frame buffer"
        # http://www.karoltomala.com/blog/?p=679
        disp_no = os.getenv("DISPLAY")
        if disp_no:
            print "I'm running under X display = {0}".format(disp_no)

        # Check which frame buffer drivers are available
        # Start with fbcon since directfb hangs with composite output
        drivers = ['fbcon', 'directfb', 'svgalib']
        found = False
        for driver in drivers:
            # Make sure that SDL_VIDEODRIVER is set
            if not os.getenv('SDL_VIDEODRIVER'):
                os.putenv('SDL_VIDEODRIVER', driver)
            try:
                pygame.display.init()
            except pygame.error:
                print 'Driver: {0} failed.'.format(driver)
                continue
            found = True
            break

        if not found:
            raise Exception('No suitable video driver found!')

        size = (pygame.display.Info().current_w, pygame.display.Info().current_h)
        self.size = size
        print "Framebuffer size: %d x %d" % (size[0], size[1])
        self.screen = pygame.display.set_mode(size, pygame.FULLSCREEN)
        # Clear the screen to start
        self.screen.fill((0, 0, 0))
        # Hide the mouse
        pygame.mouse.set_visible(False)
        # Initialise font support
        pygame.font.init()
        # Render the screen
        pygame.display.update()

    def __del__(self):
        "Destructor to make sure pygame shuts down, etc."

    def display(self, text, name="Management", text_color=(255, 255, 0), timeout=30):
        padding = 20
        font_size = 45
        self.screen.fill((0, 0, 0))
        pygame.display.update()

        font = pygame.font.Font(None, font_size)

        try:
            # Render a quote
            my_rect = pygame.Rect((25, 15, self.size[0]-10, self.size[1]-10))
            text_surface = render_textrect(text, font, my_rect,
                text_color, (0,0,0), 0)
        except TextRectException:
            text_surface = render_textrect("Error loading tweet",
                font, my_rect, (255,255,0),(0,0,0), 0)

        # Blit the text
        self.screen.blit(text_surface, (15, 25))

        # Quote byline, who wrote this kernel of knowledge
        # Colored yellow, black background
        text_surface = font.render('@%s' % name,
            True, (255, 255, 0), (0, 0, 0))
        name_placement = 640 - (padding + text_surface.get_width())
        # Blit the text
        self.screen.blit(text_surface, (name_placement, self.size[1]-30))

        # Update the display
        pygame.display.update()
        time.sleep(timeout)



class mytwitter:
    def __init__(self):
        twitter_config = configure('twitter.yml')
        self.api = twitter.Api(**twitter_config)

    def search (self, search_type, term, count=5):
        try:
            if search_type == "tag":
                res = self.api.GetSearch(term="#%s"%term, count=count)
            if search_type == "user":
                res = self.api.GetUserTimeline(screen_name="@%s"%term, count=count)
        except Exception as e:
            logger.error("Problem with search for: %s" % search_type)
            logger.error("\t with term: %s" % term)
            logger.error("\t => %s" % e )
        else:
            return res

    def users (self, users=None):
        """ Expects a list of users to pick from """
        if users == None:
            users = ['@whitehouse',
                     '@ronwyden']

        return self.search("user", random.choice(users))

    def tags (self, tags=None):
        if tags == None:
            tags = ['yolo',
                    'firstworldproblems']

        return self.search("tag", random.choice(tags))



if __name__ == '__main__':
    yellow = (255, 255, 0)
    white = (255, 255, 255)
    red = (255, 0, 0)
    green = (0, 235, 0)
    blue = (0, 100, 200)
    black = (0, 0, 0)
    config_file = 'rpi_twitter.yml'
    parser = HTMLParser.HTMLParser()

    # Create an instance of the PyScope class
    try:
		scope = pyscope()
    except Exception as e:
		logger.error ("Error loading pygame class")
		logger.error ("\t=> %s" % e)
		pygame.quit()

    ip = get_ip_address()
    if ip:
        scope.display("Our IP appears to be: %s" % ip, text_color=yellow, timeout=10)
    else:
        scope.display("Problem reading ip address, we may not work")

    try:
        twit = mytwitter()
    except Exception as e:
        logger.error ("Error loading twitter instance")
        logger.error ("\t=> %s" % e)

    # Begin main application loop
    while True:
        new_cfg = autoreload_config_file(config_file)
        if new_cfg:
            cfg = new_cfg
        choice = random.choice(['users','tags'])
        methodtoCall = getattr(twit, choice)
        text_color = random.choice([green,blue,yellow,red,white])
        if cfg:
            status = methodtoCall(cfg[choice])
        else:
            status = methodtoCall()
        try:
            for mesg in status:
                scope.display(parser.unescape(mesg.text), mesg.user.screen_name, text_color)
        except Exception as e:
            logger.error ("Error reading status")
            logger.error ("\t=> %s" % e)
            pygame.quit()

